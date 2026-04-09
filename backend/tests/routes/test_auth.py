"""Tests for authentication routes.

Endpoints under test:
- GET  /auth/providers  → 200 with provider list (public, no auth)

Requirements: 6.1, 6.2
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apis.app_api.auth.routes import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Minimal FastAPI app mounting only the auth router."""
    _app = FastAPI()
    _app.include_router(router)
    return _app


@pytest.fixture
def client(app):
    """TestClient bound to the minimal auth app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Requirement 6.1: GET /auth/providers returns provider list
# ---------------------------------------------------------------------------


class TestListAuthProviders:
    """GET /auth/providers returns enabled providers."""

    def test_returns_200_with_provider_list(self, client):
        """Req 6.1: Should return 200 with a list of configured providers."""
        mock_repo = AsyncMock()
        mock_repo.enabled = True
        mock_repo.list_providers = AsyncMock(
            return_value=[
                MagicMock(
                    provider_id="okta",
                    display_name="Okta",
                    logo_url="https://example.com/okta.png",
                    button_color="#0066CC",
                ),
            ]
        )

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

    # -------------------------------------------------------------------
    # Requirement 6.2: Empty list when none configured
    # -------------------------------------------------------------------

    def test_returns_200_with_empty_list_when_repo_disabled(self, client):
        """Req 6.2: Should return 200 with empty list when repo is disabled."""
        mock_repo = AsyncMock()
        mock_repo.enabled = False

        with patch(
            "apis.shared.auth_providers.repository.get_auth_provider_repository",
            return_value=mock_repo,
        ):
            resp = client.get("/auth/providers")

        assert resp.status_code == 200
        assert resp.json()["providers"] == []

    def test_returns_200_with_empty_list_when_no_providers(self, client):
        """Req 6.2: Should return 200 with empty list when no providers exist."""
        mock_repo = AsyncMock()
        mock_repo.enabled = True
        mock_repo.list_providers = AsyncMock(return_value=[])

        with patch(
            "apis.shared.auth_providers.repository.get_auth_provider_repository",
            return_value=mock_repo,
        ):
            resp = client.get("/auth/providers")

        assert resp.status_code == 200
        assert resp.json()["providers"] == []

    def test_returns_200_with_empty_list_on_exception(self, client):
        """Req 6.2: Should gracefully return empty list when repo raises."""
        with patch(
            "apis.shared.auth_providers.repository.get_auth_provider_repository",
            side_effect=RuntimeError("DynamoDB unavailable"),
        ):
            resp = client.get("/auth/providers")

        assert resp.status_code == 200
        assert resp.json()["providers"] == []
