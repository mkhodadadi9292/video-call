"""Chat use cases: send and list room messages."""

from backend.application.dto import MessageDTO
from backend.application.errors import RoomNotFoundError
from backend.domain.ports.room_repository import RoomRepository


class SendMessageUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, user_id: int, text: str) -> MessageDTO:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        message = self._rooms.add_message(room_id, user_id, text)
        return MessageDTO.from_domain(message)


class ListMessagesUseCase:
    def __init__(self, rooms: RoomRepository):
        self._rooms = rooms

    def execute(self, room_id: int, page: int = 1, size: int = 50) -> list[MessageDTO]:
        if not self._rooms.get_room(room_id):
            raise RoomNotFoundError(room_id)
        return [
            MessageDTO.from_domain(m)
            for m in self._rooms.list_messages(room_id, page=page, size=size)
        ]
