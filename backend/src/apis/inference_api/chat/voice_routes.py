"""
WebSocket voice route for bidirectional speech-to-speech interaction.

Exposes VoiceAgent via WebSocket for real-time audio streaming with
AWS Nova Sonic 2. Adapted from the sample-strands-agent-with-agentcore
voice router pattern.

Protocol:
    Client → Server:
        {"type": "config", "session_id": "...", "auth_token": "...", ...}  (first message)
        {"type": "bidi_audio_input", "audio": "<base64>", "sample_rate": 16000}
        {"type": "bidi_text_input", "text": "..."}
        {"type": "ping"}
        {"type": "stop"}

    Server → Client:
        {"type": "bidi_connection_start", "connection_id": "...", "status": "connected"}
        {"type": "bidi_error", "message": "..."}
        Agent stream events (audio, transcripts, tool use, etc.)
"""

import asyncio
import json
import jwt
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from apis.shared.sessions.metadata import get_session_metadata, store_session_metadata
from apis.shared.sessions.models import SessionMetadata

logger = logging.getLogger(__name__)


def _sanitize_log(value: str) -> str:
    """Strip newlines and carriage returns to prevent log injection."""
    return str(value).replace("\n", "").replace("\r", "")

router = APIRouter(tags=["voice"])

# Track active voice sessions for debugging
_active_sessions: Dict[str, Any] = {}

# Lazy import to avoid loading bidi deps at module level
_VoiceAgentClass = None


def _get_voice_agent_class():
    """Lazily import VoiceAgent to avoid import errors when bidi not installed."""
    global _VoiceAgentClass
    if _VoiceAgentClass is None:
        from agents.main_agent.voice_agent import VoiceAgent
        _VoiceAgentClass = VoiceAgent
    return _VoiceAgentClass


def _extract_user_from_token(token: str) -> Optional[Dict[str, str]]:
    """
    Extract user claims from JWT token (trusted — no signature verification).

    Same pattern as get_current_user_trusted in auth/dependencies.py.
    WebSocket connections can't use Depends() so we handle auth manually.
    """
    if not token:
        return None

    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")
        if not user_id:
            return None
        return {
            "user_id": str(user_id),
            "email": payload.get("email") or payload.get("preferred_username") or "",
            "raw_token": token,
        }
    except jwt.DecodeError as e:
        logger.warning(f"Failed to decode voice auth token: {e}")
        return None


async def _ensure_session_metadata(session_id: str, user_id: str) -> None:
    """Create session metadata entry if one doesn't already exist.

    This makes the voice session visible in the conversations side nav.
    If the session started as a text chat, existing metadata is preserved.
    """
    try:
        existing = await get_session_metadata(session_id, user_id)
        if existing:
            logger.debug(f"Session metadata already exists for {_sanitize_log(session_id)}")
            return

        now = datetime.now(timezone.utc).isoformat()
        metadata = SessionMetadata(
            session_id=session_id,
            user_id=user_id,
            title="Voice Conversation",
            status="active",
            created_at=now,
            last_message_at=now,
            message_count=0,
            starred=False,
            tags=[],
            preferences=None,
        )
        await store_session_metadata(session_id=session_id, user_id=user_id, session_metadata=metadata)
        logger.info(f"Created session metadata for voice session {_sanitize_log(session_id)}")
    except Exception as e:
        logger.error(f"Failed to create session metadata for {_sanitize_log(session_id)}: {e}", exc_info=True)


async def _finalize_voice_session(session_id: str, user_id: str, voice_agent: Any) -> None:
    """Update session metadata and store cost/token data after voice session ends.

    Called in the finally block of voice_stream to persist usage metrics.
    """
    # Use response_start_count as fallback when turns are interrupted before completion
    completed_turns = getattr(voice_agent, "turn_count", 0)
    started_turns = getattr(voice_agent, "response_start_count", 0)
    effective_turns = max(completed_turns, started_turns)

    logger.info(
        f"Finalizing voice session {_sanitize_log(session_id)}: "
        f"completed_turns={completed_turns}, started_turns={started_turns}, "
        f"effective_turns={effective_turns}, "
        f"accumulated_usage={getattr(voice_agent, 'accumulated_usage', 'N/A')}, "
        f"per_turn_usage_count={len(getattr(voice_agent, 'per_turn_usage', []))}"
    )
    try:
        # Update session metadata with final turn count
        existing = await get_session_metadata(session_id, user_id)
        if existing:
            now = datetime.now(timezone.utc).isoformat()
            updated = SessionMetadata(
                session_id=session_id,
                user_id=user_id,
                title=existing.title,
                status=existing.status,
                created_at=existing.created_at,
                last_message_at=now,
                message_count=existing.message_count + effective_turns,
                starred=existing.starred,
                tags=existing.tags,
                preferences=existing.preferences,
            )
            await store_session_metadata(session_id=session_id, user_id=user_id, session_metadata=updated)
            logger.info(f"Updated voice session metadata: turns={effective_turns}, session={_sanitize_log(session_id)}")
    except Exception as e:
        logger.error(f"Failed to update session metadata for {_sanitize_log(session_id)}: {e}", exc_info=True)

    # Store metadata for each assistant message in the voice session.
    # BidiAgent may split responses into multiple messages, so we can't assume
    # a strict user/assistant alternating pattern. Instead, read the actual messages
    # from AgentCore Memory and find which indices are assistant messages.
    try:
        import asyncio
        from agents.main_agent.config.constants import Defaults

        accumulated_usage = getattr(voice_agent, "accumulated_usage", {})
        has_usage = (accumulated_usage.get("inputTokens", 0) + accumulated_usage.get("outputTokens", 0)) > 0

        if not has_usage:
            logger.info(f"No voice usage to record metadata for session {_sanitize_log(session_id)}")
            return

        from apis.shared.sessions.models import Attribution, MessageMetadata, ModelInfo, TokenUsage
        from apis.shared.sessions.metadata import store_message_metadata

        model_id = getattr(voice_agent, "voice_model_id", "amazon.nova-2-sonic-v1:0")
        model_info = ModelInfo(
            model_id=model_id,
            model_name="Nova Sonic 2",
            provider="bedrock",
        )

        # Read actual messages from AgentCore Memory to find assistant indices
        assistant_indices = []
        try:
            session_manager = voice_agent.session_manager
            if hasattr(session_manager, "list_messages"):
                messages = await asyncio.to_thread(
                    session_manager.list_messages,
                    session_id,
                    Defaults.VOICE_AGENT_ID,
                )
                for idx, msg in enumerate(messages or []):
                    inner = getattr(msg, "message", msg)
                    role = inner.get("role") if isinstance(inner, dict) else getattr(inner, "role", None)
                    if role == "assistant":
                        assistant_indices.append(idx)
                logger.info(f"Voice session messages: {len(messages or [])} total, assistant at indices {assistant_indices}")
        except Exception as msg_err:
            logger.warning(f"Could not read voice messages for metadata: {msg_err}")

        if not assistant_indices:
            # Fallback: store a single record at index 1 (most common position)
            assistant_indices = [1]
            logger.info("No assistant messages found, using fallback index [1]")

        # Get pricing
        pricing = None
        try:
            from apis.shared.costs.calculator import CostCalculator
            from apis.shared.costs.pricing_config import get_model_pricing

            pricing = await get_model_pricing(model_id)
        except Exception as cost_err:
            logger.debug(f"Cost calculation unavailable for voice: {cost_err}")

        # Store cumulative session usage on the LAST assistant message only.
        # Nova Sonic reports cumulative totals for the whole connection, so
        # splitting across messages would be misleading. The last message
        # carries the full session cost; earlier messages get no badge.
        last_idx = assistant_indices[-1]
        input_tokens = accumulated_usage.get("inputTokens", 0)
        output_tokens = accumulated_usage.get("outputTokens", 0)
        total_tokens = input_tokens + output_tokens

        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        attribution = Attribution(
            user_id=user_id,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        cost = None
        if pricing and total_tokens > 0:
            try:
                total_cost, breakdown = CostCalculator.calculate_message_cost(accumulated_usage, pricing)
                cost = {
                    "total": total_cost,
                    "inputCost": breakdown.input_cost,
                    "outputCost": breakdown.output_cost,
                    "cacheReadCost": breakdown.cache_read_cost,
                    "cacheWriteCost": breakdown.cache_write_cost,
                }
            except Exception:
                pass

        message_metadata = MessageMetadata(
            token_usage=token_usage,
            model_info=model_info,
            attribution=attribution,
            cost=cost,
        )

        await store_message_metadata(
            session_id=session_id,
            user_id=user_id,
            message_id=f"voice:{last_idx}",
            message_metadata=message_metadata,
        )

        logger.info(
            f"Stored voice metadata on last assistant message (index {last_idx}), "
            f"usage={accumulated_usage}, session={_sanitize_log(session_id)}"
        )
    except Exception as e:
        logger.error(f"Failed to store voice cost metadata for {_sanitize_log(session_id)}: {e}", exc_info=True)


def _get_param_from_request(websocket: WebSocket, header_suffix: str, query_param: Optional[str]) -> Optional[str]:
    """Extract param from AgentCore custom header (cloud) or query param (local)."""
    header_name = f"x-amzn-bedrock-agentcore-runtime-custom-{header_suffix}"
    custom_header = websocket.headers.get(header_name)
    if custom_header:
        return custom_header
    return query_param


def _get_enabled_tools_from_request(websocket: WebSocket, query_param: Optional[str]) -> Optional[list]:
    """Extract enabled_tools from AgentCore custom header or query param."""
    tools_json = _get_param_from_request(websocket, "enabled-tools", query_param)
    if not tools_json:
        return None
    try:
        return json.loads(tools_json)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid enabled_tools JSON: {_sanitize_log(str(e))}")
        return None


@router.websocket("/voice/stream")
async def voice_stream(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    enabled_tools: Optional[str] = None,
    token: Optional[str] = None,
):
    """Bidirectional voice streaming endpoint (direct / local-dev path).

    In cloud, voice traffic arrives via ``/ws`` (the AgentCore Runtime
    routes all WebSocket connections there). This endpoint remains for local
    development, where the BFF voice proxy connects directly to
    ``ws://localhost:8001/voice/stream`` without a Runtime gateway.
    """
    await websocket.accept()

    session_id = _get_param_from_request(websocket, "session-id", session_id)
    user_id = _get_param_from_request(websocket, "user-id", user_id)
    enabled_tools_list = _get_enabled_tools_from_request(websocket, enabled_tools)
    auth_token = _get_param_from_request(websocket, "auth-token", token) or ""

    try:
        first_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        logger.info("Voice config received from client message")
    except asyncio.TimeoutError:
        logger.warning("No config message received within 10s, using query params")
        first_msg = {}
    except Exception as exc:
        logger.warning("Error reading config message: %s", exc)
        first_msg = {}

    await _run_voice_session(
        websocket=websocket,
        first_msg=first_msg,
        session_id=session_id,
        user_id=user_id,
        enabled_tools_list=enabled_tools_list,
        auth_token=auth_token,
    )


async def _receive_from_client(
    websocket: WebSocket, voice_agent: Any, session_id: str
) -> None:
    """Receive messages from client and dispatch to voice agent."""
    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type", "")

            if msg_type == "bidi_audio_input":
                audio = msg.get("audio", "")
                sample_rate = msg.get("sample_rate", 16000)
                await voice_agent.send_audio(audio, sample_rate)

            elif msg_type == "bidi_text_input":
                text = msg.get("text", "")
                if text:
                    await voice_agent.send_text(text)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "stop":
                logger.info(f"Client requested stop: session={_sanitize_log(session_id)}")
                break

            else:
                logger.debug(f"Unknown message type: {_sanitize_log(msg_type)}")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected (receive): session={_sanitize_log(session_id)}")
    except asyncio.CancelledError:
        logger.debug(f"Receive task cancelled: session={_sanitize_log(session_id)}")
        raise


async def _send_to_client(
    websocket: WebSocket, voice_agent: Any, session_id: str
) -> None:
    """Stream events from voice agent to client.

    VoiceAgent.receive_events() yields dicts from BidiAgent.receive() — each dict
    has a 'type' field (e.g. 'bidi_audio_stream', 'bidi_transcript_stream',
    'bidi_response_complete', etc.).
    """
    try:
        async for event in voice_agent.receive_events():
            try:
                if isinstance(event, dict):
                    await websocket.send_json(event)
                else:
                    await websocket.send_json({
                        "type": "bidi_event",
                        "data": str(event),
                    })
            except WebSocketDisconnect:
                logger.info(f"Client disconnected during send: session={_sanitize_log(session_id)}")
                return
            except Exception as e:
                logger.warning(f"Error sending event to client: {e}")

    except asyncio.CancelledError:
        logger.debug(f"Send task cancelled: session={_sanitize_log(session_id)}")
        raise
    except Exception as e:
        logger.error(f"Error in send_to_client: {e}")


# --- Debug endpoints ---

@router.get("/voice/sessions")
async def list_voice_sessions():
    """List active voice sessions (for debugging)."""
    return {
        "active_sessions": list(_active_sessions.keys()),
        "count": len(_active_sessions),
    }


@router.delete("/voice/sessions/{session_id}")
async def stop_voice_session(session_id: str):
    """Force-stop a voice session (for debugging)."""
    agent = _active_sessions.get(session_id)
    if not agent:
        return {"status": "not_found", "session_id": session_id}

    try:
        await agent.stop()
    except Exception as e:
        logger.error(f"Error force-stopping session {_sanitize_log(session_id)}: {e}")

    _active_sessions.pop(session_id, None)
    return {"status": "stopped", "session_id": session_id}


# =============================================================================
# /ws — AgentCore Runtime entry point
#
# The AgentCore Runtime gateway routes ALL WebSocket connections to /ws on
# the container (port 8080), regardless of whether the caller intended a
# chat turn or a voice session. This handler reads the first message to
# determine intent and dispatches accordingly:
#
#   {"type": "chat_invocation", ...}  →  _handle_ws_chat
#   {"type": "config", ...}           →  _run_voice_session (voice / bidi audio)
#
# AgentCoreContextMiddleware (BaseHTTPMiddleware) does not intercept
# WebSocket connections, so this handler sets BedrockAgentCoreContext
# manually from the upgrade headers before dispatching.
# =============================================================================


def _build_user_from_token(auth_token: str) -> Optional["User"]:
    """Construct a User from a JWT access token without signature verification.

    Mirrors get_current_user_trusted (auth/dependencies.py) for contexts
    where FastAPI Depends() is unavailable (WebSocket handlers).
    """
    from apis.shared.auth.models import User

    if not auth_token:
        return None
    try:
        payload = jwt.decode(auth_token, options={"verify_signature": False})
        user_id = payload.get("sub")
        if not user_id:
            return None
        email = payload.get("email") or payload.get("preferred_username") or ""
        name = payload.get("name") or payload.get("given_name") or email
        # Roles may live in Cognito groups or a custom claim.
        roles: list[str] = (
            payload.get("cognito:groups")
            or payload.get("custom:roles")
            or payload.get("roles")
            or []
        )
        if isinstance(roles, str):
            roles = [r.strip() for r in roles.split(",") if r.strip()]
        return User(
            user_id=str(user_id),
            email=email,
            name=name,
            roles=roles,
            picture=payload.get("picture"),
            raw_token=auth_token,
        )
    except jwt.DecodeError as exc:
        logger.warning("Failed to decode auth token in /ws handler: %s", exc)
        return None


def _set_agentcore_context_from_ws(websocket: WebSocket) -> None:
    """Populate BedrockAgentCoreContext from WebSocket upgrade headers.

    AgentCoreContextMiddleware only handles HTTP; for WebSocket connections
    the Runtime injects the same headers onto the upgrade request, so we
    read them directly from websocket.headers here.
    """
    from bedrock_agentcore.runtime import BedrockAgentCoreContext
    from apis.shared.middleware.agentcore_context import (
        HEADER_OAUTH2_CALLBACK_URL,
        HEADER_REQUEST_ID,
        HEADER_SESSION_ID,
        HEADER_WORKLOAD_ACCESS_TOKEN,
        _is_safe_callback_url,
    )

    workload_token = websocket.headers.get(HEADER_WORKLOAD_ACCESS_TOKEN)
    if workload_token:
        BedrockAgentCoreContext.set_workload_access_token(workload_token)

    callback_url = websocket.headers.get(HEADER_OAUTH2_CALLBACK_URL)
    if callback_url and _is_safe_callback_url(callback_url):
        BedrockAgentCoreContext.set_oauth2_callback_url(callback_url)

    session_id_header = websocket.headers.get(HEADER_SESSION_ID)
    if session_id_header:
        BedrockAgentCoreContext.set_request_context(
            request_id=websocket.headers.get(HEADER_REQUEST_ID, ""),
            session_id=session_id_header,
        )


async def _handle_ws_chat(websocket: WebSocket, config_msg: dict) -> None:
    """Handle a ``chat_invocation`` message arriving over WebSocket.

    Parses the InvocationRequest from the message body, sets the
    OAuth2CallbackUrl in BedrockAgentCoreContext (it travels in the message
    body because WebSocket upgrade headers can't carry it through the Runtime
    gateway), then calls the standard invocations handler and streams each
    SSE chunk back as a WebSocket text frame.
    """
    from bedrock_agentcore.runtime import BedrockAgentCoreContext
    from apis.shared.middleware.agentcore_context import _is_safe_callback_url
    from apis.inference_api.chat.routes import invocations
    from apis.inference_api.chat.models import InvocationRequest

    auth_token = config_msg.get("auth_token", "")
    body_data = config_msg.get("body", {})
    oauth_callback_url = config_msg.get("oauth2_callback_url")

    # OAuth2CallbackUrl arrives in the message body (can't come via headers
    # through the Runtime WS gateway). Validate and set in context so
    # IdentityClient OAuth consent flows work correctly.
    if oauth_callback_url and _is_safe_callback_url(oauth_callback_url):
        BedrockAgentCoreContext.set_oauth2_callback_url(oauth_callback_url)
    elif oauth_callback_url:
        logger.warning(
            "Rejected OAuth2CallbackUrl in chat_invocation: not in allowlist"
        )

    user = _build_user_from_token(auth_token)
    if not user:
        await websocket.send_text(
            f"event: stream_error\ndata: {json.dumps({'message': 'Authentication required'})}\n\n"
        )
        await websocket.send_text("event: done\ndata: {}\n\n")
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        invocation_request = InvocationRequest(**body_data)
    except Exception as exc:
        logger.warning("Invalid chat_invocation body: %s", exc)
        await websocket.send_text(
            f"event: stream_error\ndata: {json.dumps({'message': f'Invalid request: {exc}'})}\n\n"
        )
        await websocket.send_text("event: done\ndata: {}\n\n")
        return

    logger.info(
        "WS chat_invocation: session=%s user=%s",
        _sanitize_log(invocation_request.session_id),
        _sanitize_log(user.user_id),
    )

    try:
        response = await invocations(request=invocation_request, current_user=user)
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
            if chunk:
                await websocket.send_text(chunk)
    except WebSocketDisconnect:
        logger.info(
            "Chat WS client disconnected: session=%s",
            _sanitize_log(invocation_request.session_id),
        )
    except HTTPException as exc:
        # Surface structured HTTP errors (e.g. 422 from empty assistant instructions)
        # as stream_error SSE events so the browser UI shows the real message.
        logger.warning(
            "Chat invocation returned HTTP %d for session=%s: %s",
            exc.status_code,
            _sanitize_log(invocation_request.session_id),
            exc.detail,
        )
        try:
            await websocket.send_text(
                f"event: stream_error\ndata: {json.dumps({'message': str(exc.detail)})}\n\n"
            )
            await websocket.send_text("event: done\ndata: {}\n\n")
        except Exception:
            pass
    except Exception as exc:
        logger.error("Chat invocation error in /ws handler: %s", exc, exc_info=True)
        try:
            await websocket.send_text(
                f"event: stream_error\ndata: {json.dumps({'message': 'Internal error'})}\n\n"
            )
            await websocket.send_text("event: done\ndata: {}\n\n")
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _run_voice_session(
    websocket: WebSocket,
    first_msg: dict,
    session_id: Optional[str],
    user_id: Optional[str],
    enabled_tools_list: Optional[list],
    auth_token: str,
) -> None:
    """Core voice session logic — shared by /voice/stream and /ws (voice path).

    Assumes the WebSocket has already been accepted and the first config
    message has already been read by the caller.
    """
    # Apply overrides from the config message
    if first_msg.get("type") == "config":
        session_id = first_msg.get("session_id") or session_id
        user_id = first_msg.get("user_id") or user_id
        enabled_tools_list = first_msg.get("enabled_tools") or enabled_tools_list
        auth_token = first_msg.get("auth_token") or auth_token

    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info("Generated new voice session ID: %s", _sanitize_log(session_id))

    if not user_id and auth_token:
        user_info = _extract_user_from_token(auth_token)
        if user_info:
            user_id = user_info["user_id"]

    if not user_id:
        await websocket.send_json({"type": "bidi_error", "message": "Authentication required"})
        await websocket.close(code=4001, reason="Authentication required")
        return

    logger.info(
        "Voice WebSocket connected: session=%s user=%s tools=%d auth=%s",
        _sanitize_log(session_id),
        _sanitize_log(user_id),
        len(enabled_tools_list or []),
        "present" if auth_token else "missing",
    )

    voice_agent = None

    try:
        VoiceAgent = _get_voice_agent_class()
        voice_agent = VoiceAgent(
            session_id=session_id,
            user_id=user_id,
            auth_token=auth_token,
            enabled_tools=enabled_tools_list,
        )

        _active_sessions[session_id] = voice_agent

        await websocket.send_json({
            "type": "bidi_connection_start",
            "connection_id": session_id,
            "status": "connected",
        })

        await voice_agent.start()
        await _ensure_session_metadata(session_id, user_id)

        receive_task = asyncio.create_task(
            _receive_from_client(websocket, voice_agent, session_id)
        )
        send_task = asyncio.create_task(
            _send_to_client(websocket, voice_agent, session_id)
        )

        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        for task in done:
            if task.exception():
                logger.error("Voice task error: %s", task.exception())

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected: session=%s", _sanitize_log(session_id))
    except Exception as exc:
        logger.error("Voice stream error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"type": "bidi_error", "message": str(exc)})
        except Exception:
            pass
    finally:
        _active_sessions.pop(session_id, None)
        if voice_agent and user_id:
            try:
                await voice_agent.stop()
            except BaseException as exc:
                logger.debug("Voice agent stop: %s: %s", type(exc).__name__, exc)
            try:
                await voice_agent.drain_remaining_events(timeout=3.0)
            except BaseException as exc:
                logger.debug("Voice event drain: %s: %s", type(exc).__name__, exc)
            try:
                await _finalize_voice_session(session_id, user_id, voice_agent)
            except BaseException as exc:
                logger.debug("Voice session finalization error: %s: %s", type(exc).__name__, exc)
        try:
            await websocket.close()
        except BaseException:
            pass
        logger.info("Voice session cleaned up: %s", _sanitize_log(session_id))


@router.websocket("/ws")
async def ws_stream(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    enabled_tools: Optional[str] = None,
    token: Optional[str] = None,
):
    """AgentCore Runtime WebSocket entry point.

    The Runtime routes all WebSocket connections here regardless of whether
    the caller intends a chat turn or a voice session. Dispatches based on
    the ``type`` field of the first message:

    - ``chat_invocation``: SSE chat stream relayed as WebSocket text frames.
    - ``config``: bidirectional voice session (Nova Sonic).
    """
    await websocket.accept()

    # AgentCoreContextMiddleware (BaseHTTPMiddleware) is bypassed for WebSocket
    # connections, so populate BedrockAgentCoreContext from upgrade headers here.
    _set_agentcore_context_from_ws(websocket)

    # Resolve params from AgentCore custom headers or query params.
    resolved_session_id = _get_param_from_request(websocket, "session-id", session_id)
    resolved_user_id = _get_param_from_request(websocket, "user-id", user_id)
    enabled_tools_list = _get_enabled_tools_from_request(websocket, enabled_tools)
    auth_token = _get_param_from_request(websocket, "auth-token", token) or ""

    try:
        first_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("/ws: no first message within 10s — closing")
        await websocket.close(code=4000, reason="First message timeout")
        return
    except Exception as exc:
        logger.warning("/ws: error reading first message: %s", exc)
        await websocket.close(code=4000, reason="Protocol error")
        return

    msg_type = first_msg.get("type")

    if msg_type == "chat_invocation":
        await _handle_ws_chat(websocket, first_msg)
    elif msg_type == "config":
        await _run_voice_session(
            websocket=websocket,
            first_msg=first_msg,
            session_id=resolved_session_id,
            user_id=resolved_user_id,
            enabled_tools_list=enabled_tools_list,
            auth_token=auth_token,
        )
    else:
        logger.warning("/ws: unknown first message type %r — closing", msg_type)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {msg_type!r}. Expected 'chat_invocation' or 'config'.",
            })
        except Exception:
            pass
        await websocket.close(code=4000, reason="Unknown message type")