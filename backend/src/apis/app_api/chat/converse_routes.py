"""Proxy for the API-key authenticated Bedrock Converse endpoint.

Forwards /chat/api-converse requests to the Inference API, which handles
cost accounting, quota enforcement, and the actual Bedrock call. This
ensures a single code path for all API-key traffic regardless of which
URL external consumers use.

In production the Inference API lives on a separate Fargate service
(AgentCore Runtime) reachable via INFERENCE_API_URL. Locally it defaults
to http://localhost:8001.
"""

import logging
import os

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["api-converse"])

_INFERENCE_API_URL = os.environ.get("INFERENCE_API_URL", "http://localhost:8001")


@router.post(
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
