"""Admin users API module for user lookup and management."""

from .routes import router
from .service import UserAdminService

__all__ = [
    "router",
    "UserAdminService",
]
