"""Tests for the BFF chat proxy.

Covers the proxy mechanics in isolation — auth gate, first-message body
construction, SSE relay, URL resolution, and error mapping.

The proxy now speaks WebSocket to the upstream (AgentCore Runtime /ws) rather
than HTTP. Tests mock at the ``_build_aiohttp_session`` seam so they don't
need a live WebSocket server.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Callable, List, Optional

import aiohttp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apis.app_api.chat import proxy_routes
from apis.app_api.chat.proxy_routes import _build_upstream_ws_url, router as proxy_router
from apis.shared.auth.dependencies import get_current_user_from_session
from apis.shared.auth.models import User
from apis.shared.sessions_bff.models import SessionRecord


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _record() -> SessionRecord:
    now = int(time.time())
    return SessionRecord(
        session_id="sess-001",
        user_id="user-sub",
        username="alice",
        cognito_access_token="access.token.value",
        cognito_refresh_token="refresh.token.value",
        id_token="id.token.value",
        access_token_exp=now + 3600,
        csrf_secret="csrf-secret",
        created_at=now,
        last_seen_at=now,
        ttl=now + 28800,
    )


def _user(*, raw_token: str = "access.token.value") -> User:
    user = User(
        email="alice@example.com",
        user_id="user-sub",
        name="Alice",
        roles=["user"],
    )
    user.raw_token = raw_token
    return user


class _AttachSession(BaseHTTPMiddleware):
    """Minimal stand-in for SessionRefreshMiddleware — sets bff_session."""

    def __init__(self, app, record: Optional[SessionRecord]) -> None:
        super().__init__(app)
        self._record = record

    async def dispatch(self, request, call_next):
        if self._record is not None:
            request.state.bff_session = self._record
        return await call_next(request)


def _build_app(
    *,
    record: Optional[SessionRecord] = None,
    user_override: Optional[User] = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(_AttachSession, record=record)
    app.include_router(proxy_router)
    if user_override is not None:
        app.dependency_overrides[get_current_user_from_session] = lambda: user_override
    return app


class _FakeWSMessage:
    """Minimal stand-in for ``aiohttp.WSMessage``."""

    def __init__(self, type: aiohttp.WSMsgType, data: str = "") -> None:
        self.type = type
        self.data = data


class _FakeWS:
    """Async context manager / async iterator that yields pre-canned WS frames.

    ``sent`` accumulates every string passed to ``send_str`` so tests can
    assert what the proxy transmitted upstream.
    """

    def __init__(self, messages: List[_FakeWSMessage]) -> None:
        self._messages = list(messages)
        self.sent: List[str] = []

    async def send_str(self, text: str) -> None:
        self.sent.append(text)

    def __aiter__(self):
        return self

    async def __anext__(self) -> _FakeWSMessage:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def __aenter__(self) -> "_FakeWS":
        return self

    async def __aexit__(self, *_) -> None:
        pass


class _FakeSession:
    """Wraps a ``_FakeWS`` as an aiohttp.ClientSession stand-in."""

    def __init__(self, ws: _FakeWS) -> None:
        self._ws = ws
        self.connect_url: Optional[str] = None
        self.connect_kwargs: dict = {}

    def ws_connect(self, url: str, **kwargs) -> _FakeWS:
        self.connect_url = url
        self.connect_kwargs = kwargs
        return self._ws

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_) -> None:
        pass


class _ErrorSession:
    """Session whose ws_connect raises an exception — simulates unreachable upstream."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def ws_connect(self, *_, **__):
        raise self._exc

    async def __aenter__(self) -> "_ErrorSession":
        return self

    async def __aexit__(self, *_) -> None:
        pass


def _sse_messages(*texts: str) -> List[_FakeWSMessage]:
    """Build TEXT WS frames from raw SSE strings."""
    return [_FakeWSMessage(aiohttp.WSMsgType.TEXT, t) for t in texts]


def _patch_session(
    monkeypatch: pytest.MonkeyPatch,
    session: object,
) -> None:
    """Replace ``_build_aiohttp_session`` with a factory that returns ``session``."""
    monkeypatch.setattr(proxy_routes, "_build_aiohttp_session", lambda _timeout: session)


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


def test_returns_401_when_no_session_attached() -> None:
    app = _build_app(record=None)
    response = TestClient(app).post("/chat/stream", json={"message": "hi"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Happy path: SSE relay
# ---------------------------------------------------------------------------


def test_relays_sse_frames_as_event_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    sse_chunks = [
        'event: message_start\ndata: {"role": "assistant"}\n\n',
        'event: content_block_delta\ndata: {"text": "hello"}\n\n',
        "event: done\ndata: {}\n\n",
    ]
    ws = _FakeWS(_sse_messages(*sse_chunks))
    _patch_session(monkeypatch, _FakeSession(ws))
    app = _build_app(record=_record(), user_override=_user())

    response = TestClient(app).post("/chat/stream", json={"message": "hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache"
    assert response.text == "".join(sse_chunks)


# ---------------------------------------------------------------------------
# First-message body construction
# ---------------------------------------------------------------------------


def test_first_message_carries_type_body_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _FakeWS(_sse_messages("event: done\ndata: {}\n\n"))
    session = _FakeSession(ws)
    _patch_session(monkeypatch, session)
    app = _build_app(record=_record(), user_override=_user(raw_token="the-token"))

    payload = {"session_id": "s1", "message": "hello"}
    TestClient(app).post("/chat/stream", json=payload)

    assert len(ws.sent) == 1
    first_msg = json.loads(ws.sent[0])
    assert first_msg["type"] == "chat_invocation"
    assert first_msg["auth_token"] == "the-token"
    assert first_msg["body"] == payload


def test_oauth2_callback_url_embedded_in_first_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """OAuth2CallbackUrl can't travel as a WebSocket upgrade header through the
    Runtime gateway, so the proxy embeds it in the first message body instead."""
    ws = _FakeWS(_sse_messages("event: done\ndata: {}\n\n"))
    session = _FakeSession(ws)
    _patch_session(monkeypatch, session)
    app = _build_app(record=_record(), user_override=_user())

    TestClient(app).post(
        "/chat/stream",
        json={"message": "hi"},
        headers={"OAuth2CallbackUrl": "https://app.example.com/oauth-complete"},
    )

    first_msg = json.loads(ws.sent[0])
    assert first_msg.get("oauth2_callback_url") == "https://app.example.com/oauth-complete"


def test_oauth2_callback_url_absent_when_caller_did_not_send_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ws = _FakeWS(_sse_messages("event: done\ndata: {}\n\n"))
    session = _FakeSession(ws)
    _patch_session(monkeypatch, session)
    app = _build_app(record=_record(), user_override=_user())

    TestClient(app).post("/chat/stream", json={"message": "hi"})

    first_msg = json.loads(ws.sent[0])
    assert "oauth2_callback_url" not in first_msg


# ---------------------------------------------------------------------------
# URL resolution (unit tests — no HTTP round-trip needed)
# ---------------------------------------------------------------------------


def test_local_dev_url_resolves_to_ws_path() -> None:
    assert _build_upstream_ws_url("http://localhost:8001") == "ws://localhost:8001/ws"


def test_named_upstream_resolves_to_ws_path() -> None:
    assert _build_upstream_ws_url("http://upstream:9999") == "ws://upstream:9999/ws"


def test_agentcore_runtime_url_encodes_arn_and_targets_ws() -> None:
    """The ARN must be percent-encoded as a single path segment; the target
    path is /ws (not /invocations) because the Runtime gateway speaks WebSocket."""
    base = (
        "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/"
        "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/foo-AbCdEf"
    )
    expected = (
        "wss://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/"
        "arn%3Aaws%3Abedrock-agentcore%3Aus-west-2%3A123456789012%3Aruntime"
        "%2Ffoo-AbCdEf/ws"
    )
    assert _build_upstream_ws_url(base) == expected


def test_targets_ws_path_via_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFERENCE_API_URL", "http://upstream:9999")
    ws = _FakeWS(_sse_messages("event: done\ndata: {}\n\n"))
    session = _FakeSession(ws)
    _patch_session(monkeypatch, session)
    app = _build_app(record=_record(), user_override=_user())

    TestClient(app).post("/chat/stream", json={"message": "hi"})

    assert session.connect_url == "ws://upstream:9999/ws"


# ---------------------------------------------------------------------------
# Auth subprotocol (cloud vs local)
# ---------------------------------------------------------------------------


def test_cloud_url_uses_bearer_subprotocol(monkeypatch: pytest.MonkeyPatch) -> None:
    """In cloud the Runtime's JWT Authorizer reads the token from
    Sec-WebSocket-Protocol, not an Authorization header."""
    monkeypatch.setenv(
        "INFERENCE_API_URL",
        "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/"
        "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/foo",
    )
    ws = _FakeWS(_sse_messages("event: done\ndata: {}\n\n"))
    session = _FakeSession(ws)
    _patch_session(monkeypatch, session)
    app = _build_app(record=_record(), user_override=_user(raw_token="tok"))

    TestClient(app).post("/chat/stream", json={"message": "hi"})

    protocols = session.connect_kwargs.get("protocols", ())
    assert any(p.startswith("base64UrlBearerAuthorization.") for p in protocols)
    assert "Authorization" not in session.connect_kwargs.get("headers", {})


def test_local_dev_url_uses_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _FakeWS(_sse_messages("event: done\ndata: {}\n\n"))
    session = _FakeSession(ws)
    _patch_session(monkeypatch, session)
    app = _build_app(record=_record(), user_override=_user(raw_token="local-token"))

    TestClient(app).post("/chat/stream", json={"message": "hi"})

    assert session.connect_kwargs.get("headers", {}).get("Authorization") == "Bearer local-token"


# ---------------------------------------------------------------------------
# Upstream error handling — errors stream as SSE events (not HTTP codes)
# because headers are committed before the generator runs.
# ---------------------------------------------------------------------------


def test_upstream_unreachable_yields_stream_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, _ErrorSession(aiohttp.ClientConnectorError(None, OSError())))
    app = _build_app(record=_record(), user_override=_user())

    response = TestClient(app).post("/chat/stream", json={"message": "hi"})

    assert response.status_code == 200
    assert "stream_error" in response.text
    assert "event: done" in response.text


def test_ws_handshake_rejected_yields_stream_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aiohttp

    class _BadHandshake(_ErrorSession):
        def ws_connect(self, *_, **__):
            raise aiohttp.WSServerHandshakeError(
                request_info=None, history=(), status=403
            )

    _patch_session(monkeypatch, _BadHandshake(Exception()))
    app = _build_app(record=_record(), user_override=_user())

    response = TestClient(app).post("/chat/stream", json={"message": "hi"})

    assert response.status_code == 200
    assert "stream_error" in response.text
    assert "event: done" in response.text


def test_invalid_json_body_yields_stream_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ws = _FakeWS([])
    _patch_session(monkeypatch, _FakeSession(ws))
    app = _build_app(record=_record(), user_override=_user())

    # Send raw non-JSON bytes
    response = TestClient(app).post(
        "/chat/stream",
        content=b"not json at all",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert "stream_error" in response.text
    # Nothing should have been sent upstream
    assert ws.sent == []