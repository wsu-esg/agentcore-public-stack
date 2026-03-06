"""OIDC authentication service with multi-provider support."""

import base64
import hashlib
import logging
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from apis.shared.auth.state_store import OIDCStateData, create_state_store

logger = logging.getLogger(__name__)


def generate_pkce_pair() -> Tuple[str, str]:
    """
    Generate PKCE code verifier and challenge (S256).

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate 32 bytes of random data for code_verifier (43-128 chars when base64 encoded)
    code_verifier = secrets.token_urlsafe(32)

    # Create code_challenge using S256: BASE64URL(SHA256(code_verifier))
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

    return code_verifier, code_challenge


class GenericOIDCAuthService:
    """Provider-agnostic OIDC auth service for dynamically configured providers."""

    def __init__(self, provider, client_secret: str, state_store):
        """
        Initialize with a specific auth provider configuration.

        Args:
            provider: AuthProvider from the database
            client_secret: Client secret from Secrets Manager
            state_store: StateStore instance for OIDC state management
        """
        self.provider = provider
        self.client_secret = client_secret
        self.client_id = provider.client_id
        self.authorization_endpoint = provider.authorization_endpoint
        self.token_endpoint = provider.token_endpoint
        self.logout_endpoint = provider.end_session_endpoint
        self.scope = provider.scopes
        self.redirect_uri = provider.redirect_uri
        self.pkce_enabled = provider.pkce_enabled
        self.state_store = state_store
        self._state_ttl = 600

    def generate_state(
        self,
        redirect_uri: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """Generate secure state, PKCE challenge, and nonce."""
        state = secrets.token_urlsafe(32)
        code_verifier, code_challenge = generate_pkce_pair()
        nonce = secrets.token_urlsafe(32)

        self.state_store.store_state(
            state=state,
            data=OIDCStateData(
                redirect_uri=redirect_uri,
                code_verifier=code_verifier if self.pkce_enabled else None,
                nonce=nonce,
                provider_id=self.provider.provider_id,
            ),
            ttl_seconds=self._state_ttl
        )
        return state, code_challenge, nonce

    def validate_state(self, state: str) -> Tuple[bool, Optional[OIDCStateData]]:
        """Validate state token and return associated OIDC data."""
        return self.state_store.get_and_delete_state(state)

    def build_authorization_url(
        self,
        state: str,
        code_challenge: str,
        nonce: str,
        redirect_uri: Optional[str] = None,
        prompt: str = "select_account"
    ) -> str:
        """Build authorization URL with PKCE and nonce."""
        redirect = redirect_uri or self.redirect_uri

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect,
            "response_mode": "query",
            "scope": self.scope,
            "state": state,
            "nonce": nonce,
            "prompt": prompt,
        }

        if self.pkce_enabled:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        return f"{self.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code_for_tokens(
        self,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        is_valid, state_data = self.validate_state(state)
        if not is_valid or state_data is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired state parameter. Please initiate login again."
            )

        redirect = state_data.redirect_uri or redirect_uri or self.redirect_uri

        token_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
            "scope": self.scope,
        }

        if self.pkce_enabled and state_data.code_verifier:
            token_data["code_verifier"] = state_data.code_verifier

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0
                )
                response.raise_for_status()
                token_response = response.json()

                # Validate nonce in ID token if present
                id_token = token_response.get("id_token")
                if id_token and state_data.nonce:
                    import jwt
                    try:
                        id_claims = jwt.decode(id_token, options={"verify_signature": False})
                        token_nonce = id_claims.get("nonce")
                        if token_nonce != state_data.nonce:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="ID token nonce validation failed."
                            )
                    except jwt.DecodeError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid ID token received."
                        )

                return {
                    "access_token": token_response.get("access_token"),
                    "refresh_token": token_response.get("refresh_token"),
                    "id_token": token_response.get("id_token"),
                    "token_type": token_response.get("token_type", "Bearer"),
                    "expires_in": token_response.get("expires_in", 3600),
                    "scope": token_response.get("scope", ""),
                    "provider_id": self.provider.provider_id,
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"Token exchange failed for provider {self.provider.provider_id}: {e.response.status_code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code for tokens."
            )
        except httpx.RequestError as e:
            logger.error(f"Token exchange request failed for provider {self.provider.provider_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable."
            )

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        token_data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": self.scope,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0
                )
                response.raise_for_status()
                token_response = response.json()

                return {
                    "access_token": token_response.get("access_token"),
                    "refresh_token": token_response.get("refresh_token") or refresh_token,
                    "id_token": token_response.get("id_token"),
                    "token_type": token_response.get("token_type", "Bearer"),
                    "expires_in": token_response.get("expires_in", 3600),
                    "scope": token_response.get("scope", ""),
                    "provider_id": self.provider.provider_id,
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token. Please login again."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to refresh access token."
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable."
            )

    def build_logout_url(self, post_logout_redirect_uri: Optional[str] = None) -> str:
        """Build logout URL for the provider."""
        if not self.logout_endpoint:
            return ""

        params = {}
        if post_logout_redirect_uri:
            params["post_logout_redirect_uri"] = post_logout_redirect_uri

        if params:
            return f"{self.logout_endpoint}?{urlencode(params)}"
        return self.logout_endpoint


async def get_generic_auth_service(provider_id: str) -> GenericOIDCAuthService:
    """
    Create a GenericOIDCAuthService for a specific auth provider.

    Args:
        provider_id: The auth provider ID to create the service for

    Returns:
        GenericOIDCAuthService configured for the provider

    Raises:
        HTTPException: If provider not found or not enabled
    """
    from apis.shared.auth_providers.service import get_auth_provider_service

    service = get_auth_provider_service()
    provider = await service.get_provider(provider_id)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication provider '{provider_id}' not found."
        )

    if not provider.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication provider '{provider_id}' is not enabled."
        )

    client_secret = await service.get_client_secret(provider_id)
    if not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Client secret not configured for provider '{provider_id}'."
        )

    state_store = create_state_store()

    return GenericOIDCAuthService(
        provider=provider,
        client_secret=client_secret,
        state_store=state_store,
    )

