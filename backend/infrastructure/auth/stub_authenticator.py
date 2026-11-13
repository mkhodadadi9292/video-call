"""Stub bearer-token authentication.

Token format: `stub-token-for-{username}`. Real JWT auth for the app's own
users is a documented TODO (the Jitsi meeting tokens ARE real JWTs — this
stub only covers our API).
"""

from backend.domain.entities import UserAccount
from backend.domain.ports.user_repository import UserRepository

TOKEN_PREFIX = "stub-token-for-"


class StubAuthenticator:
    def __init__(self, users: UserRepository):
        self._users = users

    def authenticate(self, authorization: str | None) -> UserAccount | None:
        """Resolve a UserAccount from an Authorization header, or None if invalid."""
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization.removeprefix("Bearer ").strip()
        if not token.startswith(TOKEN_PREFIX):
            return None
        username = token.removeprefix(TOKEN_PREFIX)
        if not username:
            return None
        return self._users.get_by_username(username)
