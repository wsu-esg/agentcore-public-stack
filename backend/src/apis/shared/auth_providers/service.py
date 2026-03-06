"""Service layer for OIDC authentication provider management."""

import logging
import re
from typing import List, Optional

import httpx
from fastapi import HTTPException, status

from .models import (
    AuthProvider,
    AuthProviderCreate,
    AuthProviderUpdate,
    OIDCDiscoveryResponse,
)
from .repository import AuthProviderRepository, get_auth_provider_repository

logger = logging.getLogger(__name__)


class AuthProviderService:
    """Business logic for OIDC authentication provider management."""

    def __init__(self, repository: AuthProviderRepository):
        self._repo = repository

    @property
    def enabled(self) -> bool:
        return self._repo.enabled

    # =========================================================================
    # OIDC Discovery
    # =========================================================================

    async def discover_endpoints(self, issuer_url: str) -> OIDCDiscoveryResponse:
        """
        Fetch OIDC endpoints from the provider's .well-known/openid-configuration.

        Args:
            issuer_url: The OIDC issuer URL

        Returns:
            OIDCDiscoveryResponse with discovered endpoints

        Raises:
            HTTPException: If discovery fails
        """
        discovery_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            return OIDCDiscoveryResponse(
                issuer=data.get("issuer", issuer_url),
                authorization_endpoint=data.get("authorization_endpoint"),
                token_endpoint=data.get("token_endpoint"),
                jwks_uri=data.get("jwks_uri"),
                userinfo_endpoint=data.get("userinfo_endpoint"),
                end_session_endpoint=data.get("end_session_endpoint"),
                scopes_supported=data.get("scopes_supported"),
                response_types_supported=data.get("response_types_supported"),
                claims_supported=data.get("claims_supported"),
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"OIDC discovery failed for {issuer_url}: {e.response.status_code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OIDC discovery failed: HTTP {e.response.status_code} from {discovery_url}",
            )
        except httpx.RequestError as e:
            logger.error(f"OIDC discovery request error for {issuer_url}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not reach OIDC discovery endpoint: {discovery_url}",
            )
        except Exception as e:
            logger.error(f"OIDC discovery error for {issuer_url}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OIDC discovery response from {discovery_url}",
            )

    # =========================================================================
    # Provider CRUD
    # =========================================================================

    async def create_provider(
        self, data: AuthProviderCreate, created_by: Optional[str] = None
    ) -> AuthProvider:
        """
        Create a new auth provider with optional auto-discovery.

        If endpoints are not explicitly provided and an issuer_url is set,
        endpoints are auto-discovered from .well-known/openid-configuration.
        """
        # Validate provider_id format
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", data.provider_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="provider_id must be lowercase alphanumeric with hyphens",
            )

        # Auto-discover endpoints if not all provided
        needs_discovery = not all([
            data.authorization_endpoint,
            data.token_endpoint,
            data.jwks_uri,
        ])

        if needs_discovery and data.issuer_url:
            try:
                discovered = await self.discover_endpoints(data.issuer_url)
                # Fill in missing endpoints from discovery
                if not data.authorization_endpoint:
                    data.authorization_endpoint = discovered.authorization_endpoint
                if not data.token_endpoint:
                    data.token_endpoint = discovered.token_endpoint
                if not data.jwks_uri:
                    data.jwks_uri = discovered.jwks_uri
                if not data.userinfo_endpoint:
                    data.userinfo_endpoint = discovered.userinfo_endpoint
                if not data.end_session_endpoint:
                    data.end_session_endpoint = discovered.end_session_endpoint
            except HTTPException:
                logger.warning(
                    f"Auto-discovery failed for {data.issuer_url}, "
                    "proceeding with manually provided endpoints"
                )

        # Validate user_id_pattern is a valid regex if provided
        if data.user_id_pattern:
            try:
                re.compile(data.user_id_pattern)
            except re.error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user_id_pattern regex: {e}",
                )

        return await self._repo.create_provider(data, created_by=created_by)

    async def update_provider(
        self, provider_id: str, updates: AuthProviderUpdate
    ) -> Optional[AuthProvider]:
        """Update an auth provider. Re-discovers endpoints if issuer_url changes."""
        # If issuer_url is being changed, re-discover endpoints
        if updates.issuer_url:
            try:
                discovered = await self.discover_endpoints(updates.issuer_url)
                if not updates.authorization_endpoint:
                    updates.authorization_endpoint = discovered.authorization_endpoint
                if not updates.token_endpoint:
                    updates.token_endpoint = discovered.token_endpoint
                if not updates.jwks_uri:
                    updates.jwks_uri = discovered.jwks_uri
                if not updates.userinfo_endpoint:
                    updates.userinfo_endpoint = discovered.userinfo_endpoint
                if not updates.end_session_endpoint:
                    updates.end_session_endpoint = discovered.end_session_endpoint
            except HTTPException:
                logger.warning(
                    f"Auto-discovery failed for {updates.issuer_url}, "
                    "proceeding with manually provided endpoints"
                )

        # Validate user_id_pattern if provided
        if updates.user_id_pattern:
            try:
                re.compile(updates.user_id_pattern)
            except re.error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user_id_pattern regex: {e}",
                )

        return await self._repo.update_provider(provider_id, updates)

    async def get_provider(self, provider_id: str) -> Optional[AuthProvider]:
        """Get a provider by ID."""
        return await self._repo.get_provider(provider_id)

    async def list_providers(self, enabled_only: bool = False) -> List[AuthProvider]:
        """List all providers."""
        return await self._repo.list_providers(enabled_only=enabled_only)

    async def delete_provider(self, provider_id: str) -> bool:
        """Delete a provider and its client secret."""
        return await self._repo.delete_provider(provider_id)

    async def get_client_secret(self, provider_id: str) -> Optional[str]:
        """Get client secret for a provider."""
        return await self._repo.get_client_secret(provider_id)

    async def test_provider(self, provider_id: str) -> dict:
        """
        Test provider connectivity by verifying JWKS and token endpoints are reachable.

        Returns:
            Dict with test results
        """
        provider = await self._repo.get_provider(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Auth provider '{provider_id}' not found",
            )

        results = {
            "provider_id": provider_id,
            "jwks_reachable": False,
            "discovery_reachable": False,
            "token_endpoint_reachable": False,
            "errors": [],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test JWKS endpoint
            if provider.jwks_uri:
                try:
                    resp = await client.get(provider.jwks_uri)
                    results["jwks_reachable"] = resp.status_code == 200
                    if resp.status_code != 200:
                        results["errors"].append(
                            f"JWKS endpoint returned {resp.status_code}"
                        )
                except Exception as e:
                    results["errors"].append(f"JWKS endpoint error: {str(e)}")

            # Test OIDC discovery
            discovery_url = provider.issuer_url.rstrip("/") + "/.well-known/openid-configuration"
            try:
                resp = await client.get(discovery_url)
                results["discovery_reachable"] = resp.status_code == 200
                if resp.status_code != 200:
                    results["errors"].append(
                        f"Discovery endpoint returned {resp.status_code}"
                    )
            except Exception as e:
                results["errors"].append(f"Discovery endpoint error: {str(e)}")

            # Test token endpoint (HEAD/OPTIONS only)
            if provider.token_endpoint:
                try:
                    resp = await client.options(provider.token_endpoint)
                    results["token_endpoint_reachable"] = resp.status_code < 500
                except Exception as e:
                    results["errors"].append(f"Token endpoint error: {str(e)}")

        return results


# Singleton instance
_service: Optional[AuthProviderService] = None


def get_auth_provider_service() -> AuthProviderService:
    """Get the auth provider service singleton."""
    global _service
    if _service is None:
        _service = AuthProviderService(get_auth_provider_repository())
    return _service
