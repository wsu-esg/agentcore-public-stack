"""Integration tests for auth API routes using FastAPI TestClient.

Tests the full HTTP request/response cycle for:
- GET /auth/providers

All service dependencies are mocked to isolate route logic.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis.app_api.auth.routes import router


@pytest.fixture
def app():
    """Create a minimal FastAPI app with the auth router mounted."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def client(app):
    """TestClient bound to the minimal app."""
    return TestClient(app)


class TestListAuthProviders:
    """GET /auth/providers returns enabled providers."""

    def test_returns_provider_list(self, client, make_provider):
        """Should return a list of enabled providers with public info."""
        provider = make_provider(
            provider_id="okta",
            display_name="Okta",
            logo_url="https://example.com/okta.png",
            button_color="#0066CC",
        )

        mock_repo = AsyncMock()
        mock_repo.enabled = True
        mock_repo.list_providers = AsyncMock(return_value=[provider])

        with patch(
            "apis.shared.auth_providers.repository.get_auth_provider_repository",
            return_value=mock_repo,
        ):
            resp = client.get("/auth/providers")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["providers"]) == 1
        p = body["providers"][0]
        assert p["provider_id"] == "okta"
        assert p["display_name"] == "Okta"
        assert p["logo_url"] == "https://example.com/okta.png"
        assert p["button_color"] == "#0066CC"

    def test_returns_empty_when_repo_disabled(self, client):
        """Should return empty list when provider repo is disabled."""
        mock_repo = AsyncMock()
        mock_repo.enabled = False

        with patch(
            "apis.shared.auth_providers.repository.get_auth_provider_repository",
            return_value=mock_repo,
        ):
            resp = client.get("/auth/providers")

        assert resp.status_code == 200
        assert resp.json()["providers"] == []
