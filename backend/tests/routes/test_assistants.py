"""Tests for assistants routes.

Endpoints under test:
- GET /assistants  → 200 with assistant list (authenticated)
- GET /assistants  → 401 for unauthenticated request

Requirements: 13.1, 13.2
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis.app_api.assistants.routes import router
from apis.shared.assistants.models import (
    Assistant,
    AssistantResponse,
    AssistantsListResponse,
)
from tests.routes.conftest import mock_auth_user, mock_no_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROUTES_MODULE = "apis.app_api.assistants.routes"


def _make_assistant(**overrides) -> Assistant:
    """Create a sample Assistant model for testing."""
    defaults = dict(
        assistantId="ast-001",
        ownerId="user-001",
        ownerName="Test User",
        name="My Assistant",
        description="A helpful assistant",
        instructions="You are a helpful assistant.",
        vectorIndexId="idx-001",
        visibility="PRIVATE",
        tags=["test"],
        starters=["Hello"],
        emoji="🤖",
        usageCount=0,
        createdAt="2024-01-01T00:00:00Z",
        updatedAt="2024-01-01T00:00:00Z",
        status="COMPLETE",
    )
    defaults.update(overrides)
    return Assistant.model_validate(defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Minimal FastAPI app mounting only the assistants router."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


# ---------------------------------------------------------------------------
# Requirement 13.1: Assistants endpoint returns 200 with assistant data
# ---------------------------------------------------------------------------


class TestListAssistantsAuthenticated:
    """GET /assistants returns 200 with assistant data for authenticated user."""

    def test_returns_200_with_assistants(self, app, make_user):
        """Req 13.1: Authenticated user gets 200 with assistant list."""
        user = make_user()
        mock_auth_user(app, user)

        sample = _make_assistant()

        with patch(
            f"{ROUTES_MODULE}.list_user_assistants",
            new_callable=AsyncMock,
            return_value=([sample], None),
        ), patch(
            f"{ROUTES_MODULE}.list_shared_with_user",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            f"{ROUTES_MODULE}.list_public_assistants",
            new_callable=AsyncMock,
            return_value=[],
        ):
            client = TestClient(app)
            resp = client.get("/assistants")

        assert resp.status_code == 200
        body = resp.json()
        assert "assistants" in body
        assert len(body["assistants"]) == 1
        assert body["assistants"][0]["name"] == "My Assistant"

    def test_returns_200_with_empty_list(self, app, make_user):
        """Req 13.1: Authenticated user gets 200 with empty list when no assistants."""
        user = make_user()
        mock_auth_user(app, user)

        with patch(
            f"{ROUTES_MODULE}.list_user_assistants",
            new_callable=AsyncMock,
            return_value=([], None),
        ), patch(
            f"{ROUTES_MODULE}.list_shared_with_user",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            f"{ROUTES_MODULE}.list_public_assistants",
            new_callable=AsyncMock,
            return_value=[],
        ):
            client = TestClient(app)
            resp = client.get("/assistants")

        assert resp.status_code == 200
        body = resp.json()
        assert body["assistants"] == []


# ---------------------------------------------------------------------------
# Requirement 13.2: Assistants endpoint returns 401 for unauthenticated
# ---------------------------------------------------------------------------


class TestListAssistantsUnauthenticated:
    """GET /assistants returns 401 for unauthenticated request."""

    def test_returns_401_unauthenticated(self, app, unauthenticated_client):
        """Req 13.2: Unauthenticated request gets 401."""
        client = unauthenticated_client(app)
        resp = client.get("/assistants")

        assert resp.status_code == 401