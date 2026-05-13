"""Streaming-behavior tests for the BFF chat proxy.

Verifies that SSE chunks received from the upstream WebSocket are forwarded
to the browser incrementally (not buffered), and that late-arriving events
such as ``oauth_required`` reach the client after ``message_stop``.

The proxy's streaming guarantee comes from iterating the upstream WebSocket
async-for and yielding each frame directly. These tests exercise that path
through a real uvicorn server with a mock aiohttp session that delivers
frames with a deliberate inter-chunk delay.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from typing import List

import aiohttp
import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from apis.app_api.chat import proxy_routes
from apis.app_api.chat.proxy_routes import router as proxy_router
from apis.shared.auth.dependencies import get_current_user_from_session
from apis.shared.auth.models import User

# Upstream delay between SSE chunks — short enough to keep the test fast,
# long enough that buffering vs. streaming is unambiguously distinguishable.
_UPSTREAM_GAP_SECONDS = 0.3
_TTFB_BUDGET_SECONDS = 0.2


def _user() -> User:
    user = User(
        email="alice@example.com",
        user_id="user-sub",
        name="Alice",
        roles=["user"],
    )
    user.raw_token = "access.token"
    return user


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _UvicornInThread:
    def __init__(self, app: FastAPI) -> None:
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
                lifespan="off",
                access_log=False,
            )
        )
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_UvicornInThread":
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.1):
                    return self
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("uvicorn server failed to start within 5s")

    def __exit__(self, exc_type, exc, tb) -> None:
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5.0)


class _SlowWSMessage:
    def __init__(self, type: aiohttp.WSMsgType, data: str = "") -> None:
        self.type = type
        self.data = data


class _SlowWS:
    """Async iterator that yields WSMessage objects with a deliberate delay
    between the first and second chunk — simulates a slow upstream that the
    proxy must NOT buffer before forwarding."""

    def __init__(self, frames: List[_SlowWSMessage], gap_after: int = 1) -> None:
        self._frames = list(frames)
        self._gap_after = gap_after
        self._index = 0
        self.sent: List[str] = []

    async def send_str(self, text: str) -> None:
        self.sent.append(text)

    def __aiter__(self):
        return self

    async def __anext__(self) -> _SlowWSMessage:
        if self._index >= len(self._frames):
            raise StopAsyncIteration
        if self._index == self._gap_after:
            await asyncio.sleep(_UPSTREAM_GAP_SECONDS)
        frame = self._frames[self._index]
        self._index += 1
        return frame

    async def __aenter__(self) -> "_SlowWS":
        return self

    async def __aexit__(self, *_) -> None:
        pass


class _SlowSession:
    def __init__(self, ws: _SlowWS) -> None:
        self._ws = ws

    def ws_connect(self, *_, **__) -> _SlowWS:
        return self._ws

    async def __aenter__(self) -> "_SlowSession":
        return self

    async def __aexit__(self, *_) -> None:
        pass


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(proxy_router)
    app.dependency_overrides[get_current_user_from_session] = _user
    return app


def _patch_slow_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [
        _SlowWSMessage(aiohttp.WSMsgType.TEXT, 'event: message_start\ndata: {"role": "assistant"}\n\n'),
        # gap inserted before this frame by _SlowWS
        _SlowWSMessage(aiohttp.WSMsgType.TEXT, 'event: content_block_delta\ndata: {"text": "hi"}\n\n'),
        _SlowWSMessage(aiohttp.WSMsgType.TEXT, 'event: message_stop\ndata: {"stopReason": "end_turn"}\n\n'),
        _SlowWSMessage(aiohttp.WSMsgType.TEXT, 'event: oauth_required\ndata: {"providerId":"slack"}\n\n'),
        _SlowWSMessage(aiohttp.WSMsgType.TEXT, "event: done\ndata: {}\n\n"),
    ]
    ws = _SlowWS(frames, gap_after=1)
    monkeypatch.setattr(
        proxy_routes,
        "_build_aiohttp_session",
        lambda _timeout: _SlowSession(ws),
    )


@pytest.mark.asyncio
async def test_ttfb_under_200ms_with_x_accel_buffering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First byte must arrive well under 200ms even though the upstream
    introduces a 300ms gap mid-stream. If the proxy buffers, TTFB would
    equal total stream time (~300ms) rather than the sub-ms cost of
    relaying a single WebSocket frame."""
    _patch_slow_upstream(monkeypatch)
    app = _build_app()

    with _UvicornInThread(app) as server:
        async with httpx.AsyncClient(base_url=server.url, timeout=10.0) as client:
            t0 = time.monotonic()
            async with client.stream(
                "POST", "/chat/stream", json={"message": "hi"}
            ) as response:
                ttfb = time.monotonic() - t0
                assert response.status_code == 200
                assert response.headers["x-accel-buffering"] == "no"
                assert response.headers["cache-control"] == "no-cache"
                assert response.headers["content-type"].startswith("text/event-stream")
                assert ttfb < _TTFB_BUDGET_SECONDS, (
                    f"TTFB {ttfb:.3f}s exceeded {_TTFB_BUDGET_SECONDS}s budget — "
                    "the proxy is buffering upstream before flushing headers."
                )

                chunks: List[bytes] = []
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                body = b"".join(chunks)
                total = time.monotonic() - t0

    assert total >= _UPSTREAM_GAP_SECONDS, (
        f"Total {total:.3f}s shorter than upstream gap {_UPSTREAM_GAP_SECONDS}s "
        "— upstream stream did not actually slow-yield."
    )
    assert b"oauth_required" in body
    assert b"event: done" in body