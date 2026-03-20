"""Tests for require_system_admin dependency."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from fastapi import HTTPException

from apis.shared.auth.models import User
from apis.shared.rbac.models import UserEffectivePermissions
from apis.shared.rbac.system_admin import require_system_admin


def _user(roles: list | None = None) -> User:
    return User(
        user_id="u-1",
        email="test@example.com",
        name="Test",
        roles=roles or [],
    )


def _perms(app_roles: list) -> UserEffectivePermissions:
    return UserEffectivePermissions(
        user_id="u-1",
        app_roles=app_roles,
        tools=[],
        models=[],
        quota_tier=None,
        resolved_at=datetime.now(timezone.utc).isoformat() + "Z",
    )


class TestRequireSystemAdmin:
    @pytest.mark.asyncio
    async def test_grants_access_when_system_admin_role_present(self):
        mock_service = AsyncMock()
        mock_service.resolve_user_permissions.return_value = _perms(["system_admin"])

        with patch(
            "apis.shared.rbac.service.get_app_role_service",
            return_value=mock_service,
        ):
            result = await require_system_admin(user=_user(["Admin"]))

        assert result.user_id == "u-1"
        mock_service.resolve_user_permissions.assert_called_once()

    @pytest.mark.asyncio
    async def test_denies_access_without_system_admin_role(self):
        mock_service = AsyncMock()
        mock_service.resolve_user_permissions.return_value = _perms(["default"])

        with patch(
            "apis.shared.rbac.service.get_app_role_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await require_system_admin(user=_user(["Faculty"]))

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_denies_access_on_service_error(self):
        """Fail-closed: if AppRoleService raises, deny access."""
        mock_service = AsyncMock()
        mock_service.resolve_user_permissions.side_effect = Exception("DynamoDB down")

        with patch(
            "apis.shared.rbac.service.get_app_role_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await require_system_admin(user=_user(["Admin"]))

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_denies_access_with_empty_app_roles(self):
        mock_service = AsyncMock()
        mock_service.resolve_user_permissions.return_value = _perms([])

        with patch(
            "apis.shared.rbac.service.get_app_role_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await require_system_admin(user=_user([]))

        assert exc_info.value.status_code == 403
