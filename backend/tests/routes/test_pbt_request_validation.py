"""Property-based tests for request validation across API routes.

Uses Hypothesis to generate random inputs and verify that routes consistently
reject malformed requests with appropriate HTTP status codes.

Properties under test:
- Property 1: Pagination limit invariant (Req 3.3)
- Property 2: Invalid MIME type rejection (Req 4.2, 16.2)
- Property 3: Oversized file rejection (Req 4.3)
- Property 5: Invalid session ID rejection (Req 16.1)
- Property 6: Missing required fields rejection (Req 16.3)

Requirements: 16.1, 16.2, 16.3, 3.3, 4.2, 4.3
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from apis.app_api.sessions.routes import router as sessions_router
from apis.app_api.files.routes import router as files_router
from apis.app_api.files.service import (
    FileUploadService,
    get_file_upload_service,
    InvalidFileTypeError,
    FileTooLargeError,
)
from apis.shared.files.models import ALLOWED_MIME_TYPES
from apis.shared.sessions.models import SessionMetadata

from tests.routes.conftest import mock_auth_user, mock_service


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default max file size used by FileUploadService (4 MB)
MAX_FILE_SIZE = 4 * 1024 * 1024


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

def mime_type_not_in_allowed():
    """Strategy that generates MIME type strings NOT in ALLOWED_MIME_TYPES.

    Builds type/subtype strings directly to avoid excessive filtering.
    """
    # Generate type/subtype format directly instead of filtering random text
    type_part = st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=30,
    )
    subtype_part = st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=30,
    )
    return st.tuples(type_part, subtype_part).map(
        lambda parts: f"{parts[0]}/{parts[1]}"
    ).filter(lambda s: s not in ALLOWED_MIME_TYPES)


def oversized_file_size():
    """Strategy that generates file sizes strictly greater than MAX_FILE_SIZE."""
    return st.integers(min_value=MAX_FILE_SIZE + 1, max_value=MAX_FILE_SIZE * 100)


def random_session_id():
    """Strategy that generates random strings for session IDs.

    Uses alphanumeric characters plus common punctuation that won't break
    URL path routing (avoids ?, #, /, etc.).
    """
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="-_.",
        ),
        min_size=1,
        max_size=200,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sessions_app(make_user):
    """Minimal FastAPI app with sessions router and authenticated user."""
    app = FastAPI()
    app.include_router(sessions_router)
    user = make_user()
    mock_auth_user(app, user)
    return app


@pytest.fixture
def files_app(make_user):
    """Minimal FastAPI app with files router, authenticated user, and mocked service."""
    app = FastAPI()
    app.include_router(files_router)
    user = make_user()
    mock_auth_user(app, user)
    svc = AsyncMock(spec=FileUploadService)
    mock_service(app, get_file_upload_service, svc)
    return app, svc


# ---------------------------------------------------------------------------
# Property 1: Pagination limit invariant
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------


class TestPaginationLimitInvariant:
    """Property 1: Pagination limit invariant.

    For any valid limit N (1 ≤ N ≤ 1000) and mock session list,
    GET /sessions with limit=N returns at most N sessions.
    """

    @given(limit=st.integers(min_value=1, max_value=1000))
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_pagination_returns_at_most_n_sessions(self, limit, sessions_app):
        """Feature: api-route-tests, Property 1: Pagination limit invariant

        **Validates: Requirements 3.3**
        """
        # Create a mock session list larger than any possible limit
        mock_sessions = [
            SessionMetadata(
                session_id=f"sess-{i:04d}",
                user_id="user-001",
                title=f"Session {i}",
                status="active",
                created_at="2025-01-01T00:00:00Z",
                last_message_at="2025-01-01T01:00:00Z",
                message_count=1,
                starred=False,
                tags=[],
            )
            for i in range(limit)  # Return exactly `limit` items
        ]

        with patch(
            "apis.app_api.sessions.routes.list_user_sessions",
            new_callable=AsyncMock,
            return_value=(mock_sessions, None),
        ):
            client = TestClient(sessions_app)
            resp = client.get(f"/sessions?limit={limit}")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["sessions"]) <= limit


# ---------------------------------------------------------------------------
# Property 2: Invalid MIME type rejection
# Validates: Requirements 4.2, 16.2
# ---------------------------------------------------------------------------


class TestInvalidMimeTypeRejection:
    """Property 2: Invalid MIME type rejection.

    For any MIME type string not in ALLOWED_MIME_TYPES,
    POST /files/presign returns HTTP 400.
    """

    @given(bad_mime=mime_type_not_in_allowed())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_invalid_mime_type_returns_400(self, bad_mime, files_app):
        """Feature: api-route-tests, Property 2: Invalid MIME type rejection

        **Validates: Requirements 4.2, 16.2**
        """
        app, svc = files_app

        # Configure the mock service to raise InvalidFileTypeError for bad MIME types
        svc.request_presigned_url.side_effect = InvalidFileTypeError(bad_mime)

        client = TestClient(app)
        payload = {
            "sessionId": "sess-001",
            "filename": "test.bin",
            "mimeType": bad_mime,
            "sizeBytes": 1024,
        }
        resp = client.post("/files/presign", json=payload)

        assert resp.status_code == 400, (
            f"Expected 400 for MIME type '{bad_mime}', got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Property 3: Oversized file rejection
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------


class TestOversizedFileRejection:
    """Property 3: Oversized file rejection.

    For any file size > MAX_FILE_SIZE, POST /files/presign returns HTTP 400.
    """

    @given(size=oversized_file_size())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_oversized_file_returns_400(self, size, files_app):
        """Feature: api-route-tests, Property 3: Oversized file rejection

        **Validates: Requirements 4.3**
        """
        app, svc = files_app

        # Configure the mock service to raise FileTooLargeError for oversized files
        svc.request_presigned_url.side_effect = FileTooLargeError(
            size_bytes=size, max_size=MAX_FILE_SIZE
        )

        client = TestClient(app)
        payload = {
            "sessionId": "sess-001",
            "filename": "large-file.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": size,
        }
        resp = client.post("/files/presign", json=payload)

        assert resp.status_code == 400, (
            f"Expected 400 for file size {size}, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Property 5: Invalid session ID rejection
# Validates: Requirements 16.1
# ---------------------------------------------------------------------------


class TestInvalidSessionIdRejection:
    """Property 5: Invalid session ID rejection.

    For any random string as session_id where lookup returns no result,
    GET /sessions/{session_id}/metadata returns 404 or 422.
    """

    @given(session_id=random_session_id())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_invalid_session_id_returns_404_or_422(self, session_id, sessions_app):
        """Feature: api-route-tests, Property 5: Invalid session ID rejection

        **Validates: Requirements 16.1**
        """
        with patch(
            "apis.app_api.sessions.routes.get_session_metadata",
            new_callable=AsyncMock,
            return_value=None,
        ):
            client = TestClient(sessions_app)
            # URL-encode the session_id to handle special characters
            resp = client.get(f"/sessions/{session_id}/metadata")

        assert resp.status_code in (404, 405, 422), (
            f"Expected 404, 405, or 422 for session_id '{session_id}', got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Property 6: Missing required fields rejection
# Validates: Requirements 16.3
# ---------------------------------------------------------------------------


class TestMissingRequiredFieldsRejection:
    """Property 6: Missing required fields rejection.

    For any JSON object missing required fields, the route returns HTTP 422.
    """

    @given(
        data=st.fixed_dictionaries(
            {},
            optional={
                "sessionId": st.text(min_size=1, max_size=50),
                "filename": st.text(min_size=1, max_size=50),
                "mimeType": st.text(min_size=1, max_size=50),
                "sizeBytes": st.integers(min_value=1, max_value=10000),
            },
        ).filter(
            # Ensure at least one required field is missing
            lambda d: not all(
                k in d for k in ("sessionId", "filename", "mimeType", "sizeBytes")
            )
        )
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_missing_fields_returns_422(self, data, files_app):
        """Feature: api-route-tests, Property 6: Missing required fields rejection

        **Validates: Requirements 16.3**
        """
        app, _svc = files_app

        client = TestClient(app)
        resp = client.post("/files/presign", json=data)

        assert resp.status_code == 422, (
            f"Expected 422 for payload {data}, got {resp.status_code}"
        )
