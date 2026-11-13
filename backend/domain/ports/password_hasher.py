"""Driven port: password hashing/verification."""

from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a plaintext password for storage."""

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Check a plaintext password against a stored hash."""
