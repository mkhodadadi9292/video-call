"""Room lifecycle use cases: create, list, get, end.

Each use case is a single class with one public method (SRP — the S in SOLID).
Use cases depend only on domain ports (DIP), never on concrete infrastructure.
"""

from dataclasses import replace

from backend.application.dto import ParticipantDTO, RoomDTO, RoomDetailDTO
from backend.application.errors import RoomNotFoundError
from backend.domain.entities import JitsiRoomId, Room, RoomName
from backend.domain.ports.room_repository import RoomRepository


class CreateRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, name: str, user_id: int) -> RoomDTO:
        room = Room(
            id=None,
            name=RoomName(name),
            jitsi_room_id=JitsiRoomId.generate(),
            created_by=user_id,
        )
        return RoomDTO.from_domain(self._rooms.create_room(room))


class ListRoomsUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self) -> list[RoomDTO]:
        result = []
        for room in self._rooms.list_active_rooms():
            dto = RoomDTO.from_domain(room)
            result.append(
                replace(dto, participant_count=self._rooms.count_participants(room.id))
            )
        return result


class GetRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int) -> RoomDetailDTO:
        room = self._rooms.get_room(room_id)
        if not room:
            raise RoomNotFoundError(room_id)
        participants = [ParticipantDTO.from_domain(p) for p in self._rooms.list_participants(room_id)]
        return RoomDetailDTO(
            id=room.id,
            name=room.name.value,
            jitsi_room_id=room.jitsi_room_id.value,
            created_by=room.created_by,
            is_active=room.is_active,
            created_at=room.created_at,
            participants=participants,
        )


class EndRoomUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int) -> None:
        if not self._rooms.close_room(room_id):
            raise RoomNotFoundError(room_id)
