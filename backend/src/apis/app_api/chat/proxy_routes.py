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
from apis.shared.sessions.metadata import get_session_metadata
from apis.shared.assistants.service import get_assistant_with_access_check

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


def _build_aiohttp_session(timeout: aiohttp.ClientTimeout) -> aiohttp.ClientSession:
    """Single seam for upstream aiohttp session construction.

    Tests substitute a mock here without having to patch the global
    ``aiohttp.ClientSession`` symbol, which would intercept unrelated
    aiohttp usage in the same process.
    """
    return aiohttp.ClientSession(timeout=timeout)


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

    async with _build_aiohttp_session(timeout) as session:
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


async def _resolve_assistant_system_prompt(
    body_dict: dict,
    user_id: str,
    user_email: str,
) -> dict:
    """Resolve the assistant and pre-build the system prompt in the BFF layer.

    This is the authoritative place where assistant instructions are turned
    into a system prompt.  Doing it here rather than inside inference-api
    means the logic runs in app-api — which has always owned the assistants
    DynamoDB table — and the assistant ID reaches inference-api regardless of
    any frontend timing issues.

    Resolution order for the assistant ID:
    1. ``rag_assistant_id`` already in the request body (frontend URL param).
    2. ``preferences.assistant_id`` stored in session metadata (fallback for
       continuing sessions opened from the sidebar before the Angular
       self-heal redirect fires).

    If ``interrupt_responses`` is set (OAuth resume turn) we skip: the
    snapshot's system_prompt is used by inference-api directly.

    Returns a (possibly mutated) copy of ``body_dict``.  The original dict
    is mutated in-place; callers must re-serialise to bytes afterwards.
    """
    # Resume turns reuse the paused snapshot — skip assistant resolution.
    if body_dict.get("interrupt_responses"):
        return body_dict

    # Already has a system_prompt set (e.g. preview mode) — don't overwrite.
    if body_dict.get("system_prompt"):
        return body_dict

    assistant_id: str | None = body_dict.get("rag_assistant_id")
    session_id: str | None = body_dict.get("session_id")

    # --- Step 1: fall back to session preferences when the frontend omitted it ---
    if not assistant_id and session_id:
        try:
            session_meta = await get_session_metadata(
                session_id=session_id,
                user_id=user_id,
            )
            assistant_id = (
                session_meta.preferences.assistant_id
                if session_meta and session_meta.preferences
                else None
            )
            if assistant_id:
                body_dict["rag_assistant_id"] = assistant_id
                logger.info(
                    "BFF resolved rag_assistant_id=%s from session preferences (session=%s)",
                    assistant_id,
                    session_id,
                )
        except Exception:
            logger.debug(
                "BFF could not look up session preferences for session=%s",
                session_id,
                exc_info=True,
            )

    if not assistant_id:
        # No assistant attached to this request — use the default agent.
        return body_dict

    # --- Step 2: load assistant and build system prompt ---
    try:
        assistant = await get_assistant_with_access_check(
            assistant_id=assistant_id,
            user_id=user_id,
            user_email=user_email,
        )
    except Exception:
        logger.warning(
            "BFF could not load assistant=%s — forwarding without system_prompt",
            assistant_id,
            exc_info=True,
        )
        return body_dict

    if not assistant:
        logger.warning(
            "BFF: assistant=%s not found or access denied — forwarding without system_prompt",
            assistant_id,
        )
        return body_dict

    if not assistant.instructions:
        # Empty instructions — inference-api will surface the 422 with the
        # helpful "Please edit the assistant" message.
        logger.warning(
            "BFF: assistant=%s ('%s') has no instructions — deferring 422 to inference-api",
            assistant_id,
            assistant.name,
        )
        return body_dict

    # Build the system prompt: assistant instructions first (establishes
    # persona), followed by the base prompt's general guidelines.
    # Lazy import to keep module-level deps minimal.
    from agents.main_agent.core.system_prompt_builder import SystemPromptBuilder

    base_prompt = SystemPromptBuilder().build(include_date=True)
    system_prompt = (
        f"{assistant.instructions}"
        f"\n\n---\n\n"
        f"## General Guidelines\n\n{base_prompt}"
    )
    body_dict["system_prompt"] = system_prompt
    logger.info(
        "BFF built system_prompt for assistant=%s '%s' "
        "(instructions_len=%d base_len=%d total_len=%d)",
        assistant_id,
        assistant.name,
        len(assistant.instructions),
        len(base_prompt),
        len(system_prompt),
    )
    return body_dict


async def chat_stream(
    request: Request,
    current_user: User = Depends(get_current_user_from_session),
):
    """Relay the browser's SSE chat request to inference-api via AgentCore Runtime WebSocket.

    Before forwarding the request the BFF resolves the assistant (if any) and
    builds the system prompt here in app-api.  This means:

    * The correct assistant persona is applied even when the frontend omits
      ``rag_assistant_id`` (race condition on sidebar-opened sessions).
    * Assistant loading lives in app-api — the service that owns the assistants
      table — rather than being buried inside the inference-api container.
    * inference-api still receives ``rag_assistant_id`` so it can perform RAG
      augmentation, persist the assistant to session preferences, and scope
      spreadsheet tools to the assistant's corpus.
    """
    body = await request.body()
    oauth_callback_url = request.headers.get("OAuth2CallbackUrl")

    try:
        body_dict = json.loads(body)
    except Exception:
        # Malformed JSON — pass through; _relay_chat_stream will emit the error.
        body_dict = None

    if body_dict is not None:
        body_dict = await _resolve_assistant_system_prompt(
            body_dict=body_dict,
            user_id=current_user.user_id,
            user_email=current_user.email,
        )
        body = json.dumps(body_dict).encode()

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