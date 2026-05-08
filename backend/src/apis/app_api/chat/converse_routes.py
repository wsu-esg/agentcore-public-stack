"""Proxy endpoints that forward browser requests to the AgentCore Runtime.

Two routes are provided:

1. POST /invocations  — main chat proxy.  The frontend calls this instead of
   hitting bedrock-agentcore.amazonaws.com directly, which does not return
   CORS headers.  The App API (BFF) forwards the request to the AgentCore
   Runtime URL stored in INFERENCE_API_URL, passing through the user's
   Authorization JWT and all other relevant headers.

2. POST /chat/api-converse — API-key authenticated Bedrock Converse proxy.
   Forwards to the Inference API for cost accounting and quota enforcement.

In production INFERENCE_API_URL is the AgentCore Runtime endpoint
(https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<arn>).
Locally it defaults to http://localhost:8001.
"""

import logging
import os

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invocations-proxy"])

_INFERENCE_API_URL = os.environ.get("INFERENCE_API_URL", "http://localhost:8001")


@router.post(
    "/invocations",
    summary="Main chat proxy — forwards to AgentCore Runtime (avoids browser CORS)",
    responses={
        502: {"description": "AgentCore Runtime unreachable"},
        504: {"description": "AgentCore Runtime timed out"},
    },
)
async def invocations_proxy(request: Request):
    """Forward /invocations to the AgentCore Runtime.

    The browser cannot call bedrock-agentcore.amazonaws.com directly because
    AWS does not add CORS headers to that endpoint.  This proxy runs
    server-side and passes through:
      - Authorization header (user's Cognito JWT — validated by the Runtime)
      - OAuth2CallbackUrl header (for connector consent flows)
      - qualifier query parameter
      - full request body unchanged

    The SSE stream is relayed back to the browser as-is.
    """
    # Build target URL, preserving the qualifier query param if present
    base_url = _INFERENCE_API_URL.rstrip("/")
    qualifier = request.query_params.get("qualifier")
    target_url = f"{base_url}/invocations"
    if qualifier:
        target_url = f"{target_url}?qualifier={qualifier}"

    body = await request.body()

    # Forward headers the Runtime needs; drop hop-by-hop headers
    forward_headers: dict[str, str] = {"Content-Type": "application/json"}
    for header in ("authorization", "oauth2callbackurl"):
        value = request.headers.get(header)
        if value:
            # Preserve original capitalisation expected by the Runtime
            canonical = "Authorization" if header == "authorization" else "OAuth2CallbackUrl"
            forward_headers[canonical] = value

    logger.info("Proxying /invocations to AgentCore Runtime")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.send(
                client.build_request("POST", target_url, headers=forward_headers, content=body),
                stream=True,
            )

            if response.status_code >= 400:
                error_body = await response.aread()
                await response.aclose()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_body.decode("utf-8", errors="replace"),
                )

            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                async def _stream():
                    try:
                        async for chunk in response.aiter_bytes():
                            yield chunk
                    finally:
                        await response.aclose()

                return StreamingResponse(
                    _stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            response_body = await response.aread()
            await response.aclose()
            return StreamingResponse(
                iter([response_body]),
                media_type=content_type or "application/json",
                status_code=response.status_code,
            )

    except HTTPException:
        raise
    except httpx.ConnectError:
        logger.error("Cannot reach AgentCore Runtime at %s", target_url)
        raise HTTPException(status_code=502, detail="AgentCore Runtime is unreachable")
    except httpx.TimeoutException:
        logger.error("AgentCore Runtime request timed out: %s", target_url)
        raise HTTPException(status_code=504, detail="AgentCore Runtime request timed out")
    except Exception as exc:
        logger.error("Proxy error forwarding /invocations: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Unexpected error proxying to AgentCore Runtime")


_converse_router = APIRouter(prefix="/chat", tags=["api-converse"])


@_converse_router.post(
    "/api-converse",
    summary="Converse with a Bedrock model via API key (proxied to Inference API)",
    responses={
        401: {"description": "Invalid or expired API key"},
        502: {"description": "Inference API unreachable"},
    },
)
async def api_converse_proxy(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """Thin proxy that forwards the request to the Inference API.

    The Inference API handles API-key validation, quota checks, Bedrock
    invocation, and cost recording. This proxy simply relays the request
    and response (including SSE streams) so that external consumers can
    use the App API URL for everything.
    """
    target_url = f"{_INFERENCE_API_URL}/chat/api-converse"
    body = await request.body()

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": x_api_key,
    }

    logger.info(f"Proxying api-converse to {target_url}")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            response = await client.send(
                client.build_request(
                    "POST",
                    target_url,
                    headers=headers,
                    content=body,
                ),
                stream=True,
            )

            # Non-2xx from inference API — relay the error
            if response.status_code >= 400:
                error_body = await response.aread()
                await response.aclose()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_body.decode("utf-8", errors="replace"),
                )

            # Check if the response is SSE (streaming)
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                async def stream_relay():
                    try:
                        async for chunk in response.aiter_bytes():
                            yield chunk
                    finally:
                        await response.aclose()

                return StreamingResponse(
                    stream_relay(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            # Non-streaming: read full response and return
            response_body = await response.aread()
            await response.aclose()
            return StreamingResponse(
                iter([response_body]),
                media_type=content_type or "application/json",
                status_code=response.status_code,
            )

    except HTTPException:
        raise
    except httpx.ConnectError:
        logger.error(f"Cannot reach Inference API at {target_url}")
        raise HTTPException(status_code=502, detail="Inference API is unreachable")
    except httpx.TimeoutException:
        logger.error(f"Inference API request timed out: {target_url}")
        raise HTTPException(
            status_code=504,
            detail="Inference API request timed out",
        )
    except Exception as exc:
        logger.error(f"Proxy error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="An unexpected error occurred while proxying to the Inference API",
        )

# Re-export the api-converse sub-router under the name main.py imports
converse_router = _converse_router
