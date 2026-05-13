"""BFF chat proxy — forwards browser SSE chat requests to inference-api.

Browser → CloudFront /api/* → app-api → AgentCore Runtime WebSocket /ws
                                       → inference-api /ws (chat_invocation dispatch)
                                       → SSE streamed back to browser

Cloud: connects to the AgentCore Runtime via WebSocket at the /ws path
(same network path used by voice). The request body is sent as a
``chat_invocation`` typed first message; the container streams SSE chunks
back as WebSocket text frames, which the BFF relays as text/event-stream.

Local dev: INFERENCE_API_URL is http://localhost:8001; the BFF connects via
WebSocket to ws://localhost:8001/ws and uses the same protocol. No Runtime
gateway is in the path, so no Sec-WebSocket-Protocol auth is needed.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import quote, urlsplit

import aiohttp
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from apis.shared.auth.dependencies import get_current_user_from_session
from apis.shared.auth.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["bff-chat-proxy"])

_CONNECT_TIMEOUT = 15.0
# Long enough to cover a full agent turn (model + tool calls), bounded so a
# wedged upstream eventually surfaces.
_STREAM_TIMEOUT = 300.0


def _inference_api_url() -> str:
    return os.environ.get("INFERENCE_API_URL", "http://localhost:8001")


def _build_upstream_ws_url(base_url: str) -> str:
    """Resolve the upstream WebSocket URL from ``INFERENCE_API_URL``.

    Cloud: AgentCore Runtime WebSocket endpoint at
    ``/runtimes/<encoded-arn>/ws`` — the same path used by the voice proxy.
    The Runtime routes this WebSocket to the container's ``/ws`` handler,
    which dispatches based on the first message type.

    Local dev: ``ws://localhost:8001/ws`` — the inference-api container
    directly, bypassing the Runtime gateway entirely.
    """
    parts = urlsplit(base_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    prefix = "/runtimes/"
    if parts.netloc.startswith("bedrock-agentcore.") and parts.path.startswith(prefix):
        arn = parts.path[len(prefix):]
        encoded_arn = quote(arn, safe="")
        return f"{scheme}://{parts.netloc}/runtimes/{encoded_arn}/ws"
    return f"{scheme}://{parts.netloc}/ws"


def _bearer_subprotocol(access_token: str) -> str:
    """Pack a Cognito access token into AgentCore's accepted subprotocol form.

    The Runtime's JWT Authorizer reads ``base64UrlBearerAuthorization.<b64url>``
    from ``Sec-WebSocket-Protocol`` on the upgrade.
    """
    import base64

    b64 = base64.urlsafe_b64encode(access_token.encode("utf-8")).decode("ascii")
    return f"base64UrlBearerAuthorization.{b64.rstrip('=')}"


async def _relay_chat_stream(
    body: bytes,
    access_token: str,
    oauth_callback_url: str | None,
):
    """Open a WebSocket to the upstream and relay SSE chunks as an async generator.

    Sends the InvocationRequest body as a ``chat_invocation`` config message,
    then yields each WebSocket text frame verbatim. The container's ``/ws``
    chat handler sends SSE-formatted strings
    (``event: ...\ndata: ...\n\n``) as text frames, so the BFF can relay
    them straight into a ``StreamingResponse`` without re-encoding.
    """
    base_url = _inference_api_url()
    ws_url = _build_upstream_ws_url(base_url)

    parts = urlsplit(ws_url)
    is_cloud = parts.netloc.startswith("bedrock-agentcore.")

    protocols: list[str] = []
    headers: dict[str, str] = {}
    if is_cloud:
        protocols = [_bearer_subprotocol(access_token), "base64UrlBearerAuthorization"]
    else:
        # Local dev: inference-api trusts a plain Authorization header on
        # the upgrade; the /ws handler reads auth_token from the config
        # message as the authoritative source.
        headers["Authorization"] = f"Bearer {access_token}"

    timeout = aiohttp.ClientTimeout(total=_STREAM_TIMEOUT, connect=_CONNECT_TIMEOUT)

    try:
        body_dict = json.loads(body)
    except Exception:
        yield f"event: stream_error\ndata: {json.dumps({'message': 'invalid request body'})}\n\n"
        yield "event: done\ndata: {}\n\n"
        return

    config_msg: dict = {
        "type": "chat_invocation",
        "body": body_dict,
        "auth_token": access_token,
    }
    if oauth_callback_url:
        # OAuth2CallbackUrl cannot travel as a WebSocket header through the
        # Runtime gateway, so it's embedded in the message body. The /ws
        # handler sets it in BedrockAgentCoreContext before calling invocations.
        config_msg["oauth2_callback_url"] = oauth_callback_url

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.ws_connect(
                ws_url,
                protocols=protocols or (),
                headers=headers,
                max_msg_size=0,  # unbounded — large tool results can be big
            ) as ws:
                await ws.send_str(json.dumps(config_msg, separators=(",", ":")))

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        yield msg.data
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSING,
                    ):
                        break
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("Upstream chat WS error: %s", ws.exception())
                        yield f"event: stream_error\ndata: {json.dumps({'message': 'upstream stream error'})}\n\n"
                        yield "event: done\ndata: {}\n\n"
                        break

        except aiohttp.WSServerHandshakeError as exc:
            logger.error("Chat WS handshake failed: %s", exc)
            yield f"event: stream_error\ndata: {json.dumps({'message': f'upstream rejected ({exc.status})'})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except aiohttp.ClientConnectorError as exc:
            logger.error("Chat WS connect failed: %s", exc)
            yield f"event: stream_error\ndata: {json.dumps({'message': 'upstream unreachable'})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:
            logger.error("Chat WS relay error: %s", exc, exc_info=True)
            yield f"event: stream_error\ndata: {json.dumps({'message': 'proxy error'})}\n\n"
            yield "event: done\ndata: {}\n\n"


async def chat_stream(
    request: Request,
    current_user: User = Depends(get_current_user_from_session),
):
    """Relay the browser's SSE chat request to inference-api via AgentCore Runtime WebSocket."""
    body = await request.body()
    # Forward OAuth2CallbackUrl so the container can set it in
    # BedrockAgentCoreContext for MCP OAuth consent flows.
    oauth_callback_url = request.headers.get("OAuth2CallbackUrl")

    return StreamingResponse(
        _relay_chat_stream(body, current_user.raw_token, oauth_callback_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


router.add_api_route(
    "/stream",
    chat_stream,
    methods=["POST"],
    summary="Cookie-authenticated SSE proxy to inference-api via AgentCore Runtime WebSocket",
    operation_id="chat_stream",
    responses={
        401: {"description": "No active BFF session"},
        403: {"description": "CSRF token missing or invalid"},
        502: {"description": "Inference API unreachable"},
        504: {"description": "Inference API request timed out"},
    },
)