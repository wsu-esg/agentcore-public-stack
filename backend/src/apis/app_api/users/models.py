"""User search models for sharing functionality."""

from typing import List
from pydantic import BaseModel, Field, ConfigDict


class UserSearchResult(BaseModel):
    """User search result for sharing modal."""
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId", description="User identifier")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User display name")


class UserSearchResponse(BaseModel):
    """Response containing user search results."""
    model_config = ConfigDict(populate_by_name=True)

    users: List[UserSearchResult] = Field(..., description="List of matching users")
