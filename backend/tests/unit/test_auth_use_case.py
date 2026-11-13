"""Unit tests for the LoginUseCase (Phase 4)."""

import pytest

from backend.application.errors import InvalidCredentialsError
from backend.application.use_cases.auth import LoginUseCase
from backend.tests.fakes import FakePasswordHasher, FakeUserRepository


@pytest.fixture
def users():
    return FakeUserRepository()


@pytest.fixture
def passwords():
    return FakePasswordHasher()


class TestLoginUseCase:
    def test_login_existing_user_with_correct_password(self, users, passwords):
        users.seed("alice", passwords.hash("pw"), role="user")
        dto = LoginUseCase(users, passwords).execute("alice", "pw")
        assert dto.access_token == "stub-token-for-alice"
        assert dto.username == "alice"
        assert dto.role == "user"

    def test_login_existing_user_with_wrong_password_raises(self, users, passwords):
        users.seed("alice", passwords.hash("pw"))
        with pytest.raises(InvalidCredentialsError):
            LoginUseCase(users, passwords).execute("alice", "wrong")

    def test_first_login_creates_user(self, users, passwords):
        dto = LoginUseCase(users, passwords).execute("bob", "pw")
        assert dto.role == "user"
        account = users.get_by_username("bob")
        assert account is not None
        assert account.password_hash == "hashed:pw"

    def test_first_login_with_admin_username_gets_admin_role(self, users, passwords):
        dto = LoginUseCase(users, passwords).execute("admin", "pw")
        assert dto.role == "admin"
