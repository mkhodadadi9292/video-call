"""Driven port: access to Jitsi JWT configuration (app id + secret)."""

from abc import ABC, abstractmethod

from backend.domain.entities import JitsiConfig


class JitsiConfigProvider(ABC):
    @abstractmethod
    def get(self) -> JitsiConfig | None:
        """Return the active Jitsi credentials, or None if not configured."""
