"""Participation use cases: join, leave, list participants."""

from backend.application.dto import ParticipantDTO
from backend.application.errors import RoomNotFoundError
from backend.domain.ports.room_repository import RoomRepository


class JoinRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, user_id: int) -> None:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        self._rooms.add_participant(room_id, user_id)


class LeaveRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, user_id: int) -> None:
        self._rooms.remove_participant(room_id, user_id)


class ListParticipantsUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int) -> list[ParticipantDTO]:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        return [ParticipantDTO.from_domain(p) for p in self._rooms.list_participants(room_id)]
