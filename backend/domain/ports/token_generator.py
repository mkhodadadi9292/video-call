"""Driven port: Jitsi join-token signing (JWT)."""

from abc import ABC, abstractmethod

from backend.domain.entities import JitsiConfig, Room


class RoomTokenGenerator(ABC):
    @abstractmethod
    def generate(self, room: Room, username: str, config: JitsiConfig) -> str:
        """Sign a JWT (using `config`) authorizing `username` to join `room`'s Jitsi room."""
