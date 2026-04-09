"""Authentication routes.

Only exposes the public provider listing endpoint. All authentication
flows go through Cognito directly (frontend → Cognito → IdP → Cognito → frontend).
"""

import logging

from fastapi import APIRouter

from apis.shared.auth_providers.models import (
    AuthProviderPublicInfo,
    AuthProviderPublicListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/providers",
    response_model=AuthProviderPublicListResponse,
    summary="List enabled authentication providers",
)
async def list_auth_providers() -> AuthProviderPublicListResponse:
    """
    Public endpoint (no authentication required).

    Returns enabled auth providers for the login page to display
    provider selection buttons.
    """
    try:
        from apis.shared.auth_providers.repository import get_auth_provider_repository

        repo = get_auth_provider_repository()
        if not repo.enabled:
            return AuthProviderPublicListResponse(providers=[])

        providers = await repo.list_providers(enabled_only=True)
        return AuthProviderPublicListResponse(
            providers=[
                AuthProviderPublicInfo(
                    provider_id=p.provider_id,
                    display_name=p.display_name,
                    logo_url=p.logo_url,
                    button_color=p.button_color,
                )
                for p in providers
            ]
        )
    except Exception as e:
        logger.debug(f"Error listing auth providers (may not be configured): {e}")
        return AuthProviderPublicListResponse(providers=[])
