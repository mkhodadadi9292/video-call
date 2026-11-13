"""Driven port: persistence for rooms, participants, and chat messages.

The application layer depends on this abstraction; infrastructure provides
the SQLAlchemy implementation (dependency inversion — D in SOLID).
"""

from abc import ABC, abstractmethod

from backend.domain.entities import ChatMessage, Participant, Room


class RoomRepository(ABC):
    @abstractmethod
    def create_room(self, room: Room) -> Room:
        """Persist a new room and return it with id/created_at assigned."""

    @abstractmethod
    def list_active_rooms(self) -> list[Room]:
        """All active rooms, newest first."""

    @abstractmethod
    def get_room(self, room_id: int) -> Room | None:
        """Fetch one room by id, or None."""

    @abstractmethod
    def close_room(self, room_id: int) -> Room | None:
        """Mark a room inactive. Returns the updated room, or None if missing."""

    @abstractmethod
    def add_participant(self, room_id: int, user_id: int) -> None:
        """Record that a user joined (re-join resets left_at)."""

    @abstractmethod
    def remove_participant(self, room_id: int, user_id: int) -> None:
        """Record that a user left. Idempotent."""

    @abstractmethod
    def list_participants(self, room_id: int) -> list[Participant]:
        """All participant records for a room, joined first."""

    @abstractmethod
    def count_participants(self, room_id: int) -> int:
        """Number of currently connected participants."""

    @abstractmethod
    def add_message(self, room_id: int, user_id: int, text: str) -> ChatMessage:
        """Persist a chat message and return it with id/username/created_at."""

    @abstractmethod
    def list_messages(self, room_id: int, page: int, size: int) -> list[ChatMessage]:
        """Messages for a room, oldest first, paginated."""
