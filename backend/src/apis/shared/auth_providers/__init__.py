"""Authentication provider management for configurable OIDC providers."""

from .models import AuthProvider
from .repository import AuthProviderRepository, get_auth_provider_repository
from .service import AuthProviderService, get_auth_provider_service

__all__ = [
    "AuthProvider",
    "AuthProviderRepository",
    "get_auth_provider_repository",
    "AuthProviderService",
    "get_auth_provider_service",
]
