"""Driven port: user account persistence."""

from abc import ABC, abstractmethod

from backend.domain.entities import UserAccount


class UserRepository(ABC):
    @abstractmethod
    def get_by_username(self, username: str) -> UserAccount | None:
        """Fetch a user account by username, or None."""

    @abstractmethod
    def create(self, username: str, password_hash: str, role: str) -> UserAccount:
        """Persist a new user account."""
