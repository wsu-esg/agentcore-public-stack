"""BFF chat proxy — bridges browser SSE chat requests to AgentCore via WebSocket.

`POST /chat/stream` is the cookie-authenticated entry point for the SPA.
The flow:

  Browser  → CloudFront `/api/*`  → app-api  → AgentCore Runtime `/invocations`
           (httpOnly session cookie)         (Authorization: Bearer <token>)
                    HTTP SSE ←                      WebSocket (wss://)

AgentCore's data-plane `/invocations` endpoint is WebSocket-native for
streaming. This handler:

  1. Accepts a plain HTTP POST from the browser (unchanged SPA contract).
  2. Opens a wss:// WebSocket to AgentCore, sending the request body as
     the first (and only) outbound text frame.
  3. Relays every inbound WebSocket frame back to the browser as an
     SSE `data:` event, preserving the existing SPA event-stream contract.
  4. Closes the WebSocket cleanly once AgentCore signals completion or
     the browser disconnects.

Local dev: `INFERENCE_API_URL` is `http://localhost:8001`, where
`/invocations` is a real FastAPI route on inference-api that still speaks
plain HTTP POST + SSE. The proxy detects this and falls back to the legacy
HTTP path so local developer experience is unchanged.

`SessionRefreshMiddleware` resolves the session cookie and, if the stored
Cognito access token is near expiry, refreshes it before this handler runs.
The handler forwards `current_user.raw_token` as a Bearer token. No
inference-api changes are required (architecture decision #4 in the BFF
migration plan).

The legacy in-process Bearer agent route that previously owned `/chat/stream`
was renamed to `/chat/agent-stream` in the Phase 6 cutover. The Phase 4
`/chat/proxy-stream` rolling-deploy alias was deleted in Phase 7.
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import quote, urlsplit

import httpx
import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from apis.shared.auth.dependencies import get_current_user_from_session
from apis.shared.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["bff-chat-proxy"])

# Long enough to cover a full agent turn (model + tool calls), bounded so a
# wedged upstream eventually surfaces.
_PROXY_TIMEOUT_SECONDS = 300.0

# How long to wait for the WebSocket opening handshake before giving up.
_WS_CONNECT_TIMEOUT_SECONDS = 10.0


def _inference_api_url() -> str:
    return os.environ.get("INFERENCE_API_URL", "http://localhost:8001")


def _is_agentcore(base_url: str) -> bool:
    """Return True when the configured upstream is an AgentCore Runtime endpoint."""
    return urlsplit(base_url).netloc.startswith("bedrock-agentcore.")


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def _build_ws_url(base_url: str) -> str:
    """Build the ``wss://`` WebSocket URL for AgentCore Runtime ``/invocations``.

    ``INFERENCE_API_URL`` is the AgentCore data-plane base:
        ``https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<ARN>``

    The route is::

        POST /runtimes/{agentRuntimeArn}/invocations?qualifier={qualifier}

    where ``{agentRuntimeArn}`` must be a single percent-encoded path segment
    (the ARN's literal ``/`` and ``:`` must be encoded or AWS returns 404).
    A ``qualifier`` is required; we use ``DEFAULT``.

    The ``https`` scheme is replaced with ``wss`` — AgentCore accepts the
    WebSocket upgrade on the same path.
    """
    parts = urlsplit(base_url)
    prefix = "/runtimes/"
    if parts.path.startswith(prefix):
        arn = parts.path[len(prefix):]
        encoded_arn = quote(arn, safe="")
        return (
            f"wss://{parts.netloc}/runtimes/{encoded_arn}"
            f"/invocations?qualifier=DEFAULT"
        )
    # Fallback: just swap the scheme and append /invocations. Should not be
    # reached for a well-formed AgentCore URL, but avoids a hard crash.
    scheme = "wss" if parts.scheme == "https" else "ws"
    return f"{scheme}://{parts.netloc}{parts.path}/invocations?qualifier=DEFAULT"


def _build_http_url(base_url: str) -> str:
    """Build the plain HTTP ``/invocations`` URL for local-dev inference-api."""
    return f"{base_url}/invocations"


# ---------------------------------------------------------------------------
# Upstream client factories — single seam for test substitution
# ---------------------------------------------------------------------------

def _build_http_client() -> httpx.AsyncClient:
    """HTTP client used on the local-dev fallback path.

    Tests substitute a ``MockTransport``-backed client here without having to
    monkey-patch the global ``httpx.AsyncClient`` symbol.
    """
    return httpx.AsyncClient(timeout=httpx.Timeout(_PROXY_TIMEOUT_SECONDS))


# ---------------------------------------------------------------------------
# Streaming relay helpers
# ---------------------------------------------------------------------------

async def _ws_stream_relay(
    ws_url: str,
    body: bytes,
    auth_headers: dict[str, str],
):
    """Async generator: open a WebSocket to AgentCore and yield SSE chunks.

    Each inbound WebSocket frame is emitted as a single SSE ``data:`` line so
    the SPA receives the same event-stream contract it had before.

    The generator performs a clean WebSocket close when:
    - AgentCore closes the connection normally (EOF / close frame), or
    - An exception propagates out (caller's ``StreamingResponse`` tears down
      the generator via ``aclose()``).
    """
    try:
        async with websockets.connect(
            ws_url,
            additional_headers=auth_headers,
            open_timeout=_WS_CONNECT_TIMEOUT_SECONDS,
            close_timeout=5.0,
        ) as ws:
            logger.debug("WebSocket connection established to %s", ws_url)

            # Send the SPA's request body as the first (and only) outbound frame.
            await ws.send(body.decode("utf-8"))

            # Relay every inbound frame as an SSE event.
            async for message in ws:
                # AgentCore sends JSON-encoded frames; re-wrap as SSE data lines.
                # The SPA's existing SSE parser expects `data: <payload>\n\n`.
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                yield f"data: {message}\n\n".encode()

    except websockets.exceptions.InvalidURI as exc:
        logger.error("Invalid WebSocket URI %s: %s", ws_url, exc)
        # Emit an SSE error event so the SPA can surface a meaningful message
        # rather than silently stalling.
        yield b'data: {"type":"error","detail":"Invalid upstream WebSocket URI"}\n\n'

    except (
        websockets.exceptions.WebSocketException,
        ConnectionRefusedError,
        OSError,
    ) as exc:
        logger.error("WebSocket error proxying to %s: %s", ws_url, exc, exc_info=True)
        yield b'data: {"type":"error","detail":"Upstream WebSocket connection failed"}\n\n'

    except asyncio.TimeoutError:
        logger.error("WebSocket connect timeout to %s", ws_url)
        yield b'data: {"type":"error","detail":"Upstream WebSocket timed out"}\n\n'


async def _http_stream_relay(
    http_url: str,
    body: bytes,
    auth_headers: dict[str, str],
    client: httpx.AsyncClient,
):
    """Async generator: HTTP SSE relay for the local-dev inference-api path.

    Mirrors the behaviour of the old proxy so ``localhost:8001`` keeps working
    without a WebSocket server in local dev.
    """
    try:
        async with client.stream(
            "POST", http_url, headers=auth_headers, content=body
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                detail = error_body.decode("utf-8", errors="replace")
                logger.error(
                    "Inference API returned %d: %s", response.status_code, detail
                )
                yield (
                    f'data: {{"type":"error","status":{response.status_code},'
                    f'"detail":{detail!r}}}\n\n'
                ).encode()
                return

            async for chunk in response.aiter_bytes():
                yield chunk

    except httpx.ConnectError:
        logger.error("Cannot reach local inference API at %s", http_url)
        yield b'data: {"type":"error","detail":"Inference API is unreachable"}\n\n'

    except httpx.TimeoutException:
        logger.error("Local inference API request timed out: %s", http_url)
        yield b'data: {"type":"error","detail":"Inference API request timed out"}\n\n'

    except Exception as exc:
        logger.error("HTTP proxy error: %s", exc, exc_info=True)
        yield b'data: {"type":"error","detail":"Unexpected proxy error"}\n\n'

    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------

async def chat_stream(
    request: Request,
    current_user: User = Depends(get_current_user_from_session),
):
    """Relay the SPA's chat request to AgentCore (WebSocket) or local inference-api (HTTP).

    The request body is treated as opaque bytes — schema validation lives
    on the upstream side so this handler stays decoupled from
    ``InvocationRequest``.

    For AgentCore targets the body is sent as the first WebSocket text frame
    and inbound frames are re-emitted as SSE ``data:`` events.

    For local-dev targets (``localhost``) the legacy HTTP POST + SSE relay is
    used so developers don't need a WebSocket server running locally.

    ``X-Accel-Buffering: no`` is set on the response to defeat nginx/CloudFront
    proxy buffering so SSE events (notably ``oauth_required`` after
    ``message_stop``) reach the browser without being held by an intermediary.
    """
    base_url = _inference_api_url()
    body = await request.body()

    auth_headers: dict[str, str] = {
        "Authorization": f"Bearer {current_user.raw_token}",
    }

    # Forward OAuth2CallbackUrl when the SPA supplies it. Inference-api's
    # AgentCoreContextMiddleware reads this header to scope the on-tool OAuth
    # consent landing URL to the SPA's origin (allowlisted via CORS_ORIGINS).
    # Without it, MCP-tool consent flows can't redirect back to the SPA's
    # `/oauth-complete` page and `oauth_required` SSE events are unusable.
    # Forwarded as-is — the inference-api side re-validates against its own
    # CORS_ORIGINS allowlist.
    forwarded_callback = request.headers.get("OAuth2CallbackUrl")
    if forwarded_callback:
        auth_headers["OAuth2CallbackUrl"] = forwarded_callback

    sse_headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }

    if _is_agentcore(base_url):
        # ------------------------------------------------------------------ #
        # Production path: AgentCore Runtime — WebSocket upstream             #
        # ------------------------------------------------------------------ #
        ws_url = _build_ws_url(base_url)
        logger.debug("Proxying via WebSocket to %s", ws_url)
        return StreamingResponse(
            _ws_stream_relay(ws_url, body, auth_headers),
            media_type="text/event-stream",
            headers=sse_headers,
        )

    # ---------------------------------------------------------------------- #
    # Local-dev path: plain inference-api — HTTP POST + SSE upstream          #
    # ---------------------------------------------------------------------- #
    http_url = _build_http_url(base_url)
    logger.debug("Proxying via HTTP to %s", http_url)
    http_client = _build_http_client()
    return StreamingResponse(
        _http_stream_relay(http_url, body, auth_headers, http_client),
        media_type="text/event-stream",
        headers=sse_headers,
    )


router.add_api_route(
    "/stream",
    chat_stream,
    methods=["POST"],
    summary="Cookie-authenticated SSE proxy — WebSocket upstream (AgentCore) or HTTP (local dev)",
    operation_id="chat_stream",
    responses={
        401: {"description": "No active BFF session"},
        403: {"description": "CSRF token missing or invalid"},
        502: {"description": "Upstream unreachable or WebSocket handshake failed"},
        504: {"description": "Upstream request timed out"},
    },
)