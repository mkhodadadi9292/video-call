"""Auth use case: login (self-registration on first login — stub auth).

Real JWT-based authentication for the app's own users is a documented TODO;
the token issued here is `stub-token-for-{username}`.
"""

from backend.application.dto import LoginDTO
from backend.application.errors import InvalidCredentialsError
from backend.domain.ports.password_hasher import PasswordHasher
from backend.domain.ports.user_repository import UserRepository

TOKEN_PREFIX = "stub-token-for-"


class LoginUseCase:
    def __init__(self, users: UserRepository, passwords: PasswordHasher):
        self._users = users
        self._passwords = passwords

    def execute(self, username: str, password: str) -> LoginDTO:
        account = self._users.get_by_username(username)
        if account:
            if not self._passwords.verify(password, account.password_hash):
                raise InvalidCredentialsError()
        else:
            role = "admin" if username == "admin" else "user"
            account = self._users.create(username, self._passwords.hash(password), role)
        return LoginDTO(
            access_token=f"{TOKEN_PREFIX}{account.username}",
            username=account.username,
            role=account.role,
        )
