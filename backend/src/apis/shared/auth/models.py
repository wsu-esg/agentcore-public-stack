"""Authentication models shared across API projects."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class User:
    """Authenticated user model."""
    email: str
    user_id: str
    name: str
    roles: List[str]
    picture: Optional[str] = None
    raw_token: Optional[str] = None

    def __repr__(self):
        """Redact raw_token from string representations to prevent accidental logging."""
        return (
            f"User(email={self.email!r}, user_id={self.user_id!r}, "
            f"name={self.name!r}, roles={self.roles!r})"
        )





