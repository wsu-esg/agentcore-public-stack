"""API-key authenticated Bedrock Converse endpoint on the App API.

This module mirrors the /chat/api-converse endpoint from the inference API,
allowing external API consumers to reach it via the ALB (App API) instead of
needing direct access to the AgentCore Runtime URL.

Security:
- Requests are authenticated via X-API-Key header (SHA-256 hashed lookup).
- The API key is validated and must be non-expired.
- Bedrock is called using the App API task role's IAM credentials.
- RBAC model access is enforced: users can only invoke models their roles allow.
"""

import logging
import os
from typing import AsyncGenerator

import boto3
from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from apis.app_api.auth.api_keys.service import get_api_key_service
from apis.inference_api.chat.models import ConverseRequest, ConverseResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["api-converse"])


# ---------------------------------------------------------------------------
# Helpers (mirrors inference_api/chat/converse_routes.py)
# ---------------------------------------------------------------------------


async def _validate_api_key(api_key: str):
    """Validate the raw API key and return the ValidatedApiKey, or raise 401."""
    service = get_api_key_service()
    validated = await service.validate_key(api_key)
    if validated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )
    return validated


def _get_bedrock_client():
    """Return a boto3 bedrock-runtime client."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def _build_converse_params(request: ConverseRequest) -> dict:
    """Build the kwargs dict for bedrock.converse / converse_stream."""
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

    params: dict = {"modelId": request.model_id, "messages": messages}

    if request.system_prompt:
        params["system"] = [{"text": request.system_prompt}]
    if inference_config:
        params["inferenceConfig"] = inference_config

    return params


def _extract_reasoning_and_text(content_blocks: list) -> tuple[str, str | None]:
    """Extract text and optional reasoning from Bedrock content blocks."""
    text_parts: list[str] = []
    reasoning_parts: list[str] = []

    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "reasoningContent" in block:
            rc = block["reasoningContent"]
            if "reasoningText" in rc:
                reasoning_parts.append(rc["reasoningText"]["text"])

    return (
        "\n".join(text_parts),
        "\n".join(reasoning_parts) if reasoning_parts else None,
    )


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

import json as _json


def _sse(event_type: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"event: {event_type}\ndata: {_json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------


async def _stream_converse(request: ConverseRequest) -> AsyncGenerator[str, None]:
    """Yield SSE frames from a Bedrock converse_stream call."""
    client = _get_bedrock_client()
    params = _build_converse_params(request)

    try:
        response = client.converse_stream(**params)
    except Exception as exc:
        logger.error(f"Bedrock converse_stream error: {exc}", exc_info=True)
        yield _sse("error", {"error": f"Model invocation failed: {exc}"})
        yield _sse("done", {})
        return

    yield _sse("message_start", {"model_id": request.model_id})

    stream = response.get("stream")
    if not stream:
        yield _sse("error", {"error": "No stream in response"})
        yield _sse("done", {})
        return

    for event in stream:
        if "contentBlockStart" in event:
            block = event["contentBlockStart"]
            start_data = block.get("start", {})
            if "toolUse" in start_data:
                yield _sse("content_block_start", {
                    "index": block.get("contentBlockIndex", 0),
                    "type": "tool_use",
                    "tool": start_data["toolUse"],
                })
            else:
                yield _sse("content_block_start", {
                    "index": block.get("contentBlockIndex", 0),
                    "type": "text",
                })

        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"]["delta"]
            if "text" in delta:
                yield _sse("text", {"text": delta["text"]})
            elif "reasoningContent" in delta:
                rc = delta["reasoningContent"]
                if "text" in rc:
                    yield _sse("reasoning_delta", {"text": rc["text"]})

        elif "contentBlockStop" in event:
            yield _sse("content_block_stop", {
                "index": event["contentBlockStop"].get("contentBlockIndex", 0),
            })

        elif "messageStop" in event:
            yield _sse("message_stop", {
                "stop_reason": event["messageStop"].get("stopReason"),
            })

        elif "metadata" in event:
            usage = event["metadata"].get("usage")
            if usage:
                yield _sse("metadata", {"usage": usage})

    yield _sse("done", {})


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/api-converse",
    response_model=ConverseResponse,
    responses={
        401: {"description": "Invalid or expired API key"},
        400: {"description": "Bad request"},
        502: {"description": "Model invocation failed"},
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
    try:
        validated_key = await _validate_api_key(x_api_key)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"API key validation error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Key validation failed: {exc}")

    logger.info(
        f"api-converse request from user={validated_key.user_id} "
        f"key={validated_key.key_id} model={request.model_id} "
        f"messages={len(request.messages)} stream={request.stream}"
    )

    if not request.messages:
        raise HTTPException(status_code=400, detail="messages array must not be empty")

    # Streaming path
    if request.stream:
        return StreamingResponse(
            _stream_converse(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming path
    client = _get_bedrock_client()
    params = _build_converse_params(request)

    try:
        response = client.converse(**params)
    except Exception as exc:
        logger.error(f"Bedrock converse error: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Model invocation failed: {exc}")

    output = response.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])

    text, reasoning = _extract_reasoning_and_text(content_blocks)

    return ConverseResponse(
        content=text,
        model_id=request.model_id,
        usage=response.get("usage"),
        stop_reason=response.get("stopReason"),
        reasoning=reasoning,
    )
