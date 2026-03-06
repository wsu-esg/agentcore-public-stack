"""API-key authenticated converse endpoint.

Provides a direct Bedrock Converse API wrapper authenticated via API keys
(X-API-Key header). Supports:
- Single-shot and multi-turn conversations
- Streaming (SSE) and non-streaming responses
- Reasoning models (extended thinking / reasoning content blocks)
- Multiple Bedrock model IDs
"""

import json
import logging
import os
from typing import AsyncGenerator

import boto3
from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from .models import ConverseRequest, ConverseResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["api-converse"])


# ---------------------------------------------------------------------------
# API key validation dependency
# ---------------------------------------------------------------------------

async def _validate_api_key(api_key: str):
    """Validate the raw API key and return the ValidatedApiKey, or raise 401."""
    from apis.app_api.auth.api_keys.service import get_api_key_service

    service = get_api_key_service()
    validated = await service.validate_key(api_key)
    if validated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )
    return validated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_bedrock_client():
    """Return a boto3 bedrock-runtime client."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def _build_converse_params(request: ConverseRequest) -> dict:
    """Build the kwargs dict for bedrock.converse / converse_stream."""
    # Convert messages to Bedrock Converse format
    messages = [
        {"role": m.role, "content": [{"text": m.content}]}
        for m in request.messages
    ]

    inference_config: dict = {}
    if request.temperature is not None:
        inference_config["temperature"] = request.temperature
    if request.max_tokens is not None:
        inference_config["maxTokens"] = request.max_tokens
    if request.top_p is not None:
        inference_config["topP"] = request.top_p

    params: dict = {
        "modelId": request.model_id,
        "messages": messages,
    }

    if request.system_prompt:
        params["system"] = [{"text": request.system_prompt}]

    if inference_config:
        params["inferenceConfig"] = inference_config

    return params


def _extract_reasoning_and_text(content_blocks: list) -> tuple[str, str | None]:
    """Extract text and optional reasoning from Bedrock response content blocks.

    Reasoning models (e.g. Claude with extended thinking) return a
    ``reasoningContent`` block alongside the normal ``text`` block.

    Returns:
        (text, reasoning) – reasoning is None for non-reasoning models.
    """
    text_parts: list[str] = []
    reasoning_parts: list[str] = []

    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "reasoningContent" in block:
            # Extended thinking / reasoning block
            rc = block["reasoningContent"]
            if "reasoningText" in rc:
                reasoning_parts.append(rc["reasoningText"].get("text", ""))

    text = "".join(text_parts)
    reasoning = "".join(reasoning_parts) if reasoning_parts else None
    return text, reasoning


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

async def _stream_converse(request: ConverseRequest) -> AsyncGenerator[str, None]:
    """Call Bedrock converse_stream and yield SSE events."""
    client = _get_bedrock_client()
    params = _build_converse_params(request)

    try:
        response = client.converse_stream(**params)
    except client.exceptions.ClientError as exc:
        yield _sse("error", {"error": str(exc)})
        yield _sse("done", {})
        return
    except Exception as exc:
        logger.error(f"Bedrock converse_stream error: {exc}", exc_info=True)
        yield _sse("error", {"error": str(exc)})
        yield _sse("done", {})
        return

    stream = response.get("stream")
    if not stream:
        yield _sse("error", {"error": "No stream returned from Bedrock"})
        yield _sse("done", {})
        return

    # Track state for SSE lifecycle events
    in_reasoning = False

    for event in stream:
        # --- message start ---
        if "messageStart" in event:
            role = event["messageStart"].get("role", "assistant")
            yield _sse("message_start", {"role": role})

        # --- content block start ---
        elif "contentBlockStart" in event:
            cbs = event["contentBlockStart"]
            idx = cbs.get("contentBlockIndex", 0)
            start_data = cbs.get("start", {})

            if "toolUse" in start_data:
                yield _sse("content_block_start", {
                    "contentBlockIndex": idx,
                    "type": "tool_use",
                    "toolUse": start_data["toolUse"],
                })
            else:
                yield _sse("content_block_start", {
                    "contentBlockIndex": idx,
                    "type": "text",
                })

        # --- content block delta ---
        elif "contentBlockDelta" in event:
            cbd = event["contentBlockDelta"]
            idx = cbd.get("contentBlockIndex", 0)
            delta = cbd.get("delta", {})

            if "text" in delta:
                yield _sse("content_block_delta", {
                    "contentBlockIndex": idx,
                    "type": "text",
                    "text": delta["text"],
                })
            elif "reasoningContent" in delta:
                rc = delta["reasoningContent"]
                if "text" in rc:
                    if not in_reasoning:
                        in_reasoning = True
                        yield _sse("reasoning_start", {"contentBlockIndex": idx})
                    yield _sse("reasoning_delta", {
                        "contentBlockIndex": idx,
                        "text": rc["text"],
                    })

        # --- content block stop ---
        elif "contentBlockStop" in event:
            idx = event["contentBlockStop"].get("contentBlockIndex", 0)
            if in_reasoning:
                yield _sse("reasoning_stop", {"contentBlockIndex": idx})
                in_reasoning = False
            yield _sse("content_block_stop", {"contentBlockIndex": idx})

        # --- message stop ---
        elif "messageStop" in event:
            stop_reason = event["messageStop"].get("stopReason", "end_turn")
            yield _sse("message_stop", {"stopReason": stop_reason})

        # --- metadata ---
        elif "metadata" in event:
            meta = event["metadata"]
            usage = meta.get("usage", {})
            metrics = meta.get("metrics", {})
            yield _sse("metadata", {"usage": usage, "metrics": metrics})

    yield _sse("done", {})


def _sse(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/api-converse",
    response_model=ConverseResponse,
    responses={
        200: {"description": "Non-streaming response (or SSE stream when stream=true)"},
        401: {"description": "Invalid or expired API key"},
        400: {"description": "Bad request (invalid model, empty messages, etc.)"},
    },
    summary="Converse with a Bedrock model via API key",
)
async def api_converse(
    request: ConverseRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """Direct Bedrock Converse API wrapper authenticated via API key.

    Supports streaming (SSE) and non-streaming responses, multi-turn
    conversations, and reasoning models that return extended thinking blocks.
    """
    # 1. Validate API key
    validated_key = await _validate_api_key(x_api_key)
    logger.info(
        f"api-converse request from user={validated_key.user_id} "
        f"key={validated_key.key_id} model={request.model_id} "
        f"messages={len(request.messages)} stream={request.stream}"
    )

    # 2. Basic validation
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages array must not be empty")

    # 3. Streaming path
    if request.stream:
        return StreamingResponse(
            _stream_converse(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # 4. Non-streaming path
    client = _get_bedrock_client()
    params = _build_converse_params(request)

    try:
        response = client.converse(**params)
    except Exception as exc:
        logger.error(f"Bedrock converse error: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Model invocation failed: {exc}")

    # Parse response
    output = response.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])

    text, reasoning = _extract_reasoning_and_text(content_blocks)

    usage = response.get("usage")
    stop_reason = response.get("stopReason")

    return ConverseResponse(
        content=text,
        model_id=request.model_id,
        usage=usage,
        stop_reason=stop_reason,
        reasoning=reasoning,
    )
