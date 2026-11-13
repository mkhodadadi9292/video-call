"""Token use case: issue a JWT authorizing a user to join a Jitsi room."""

from backend.application.dto import JoinTokenDTO
from backend.application.errors import JitsiConfigMissingError, RoomInactiveError, RoomNotFoundError
from backend.domain.ports.jitsi_config_provider import JitsiConfigProvider
from backend.domain.ports.room_repository import RoomRepository
from backend.domain.ports.token_generator import RoomTokenGenerator


class GenerateJoinTokenUseCase:
    def __init__(
        self,
        rooms: RoomRepository,
        tokens: RoomTokenGenerator,
        config: JitsiConfigProvider,
    ):
        self._rooms = rooms
        self._tokens = tokens
        self._config = config

    def execute(self, room_id: int, username: str) -> JoinTokenDTO:
        room = self._rooms.get_room(room_id)
        if not room:
            raise RoomNotFoundError(room_id)
        if not room.is_active:
            raise RoomInactiveError(room_id)
        config = self._config.get()
        if not config:
            raise JitsiConfigMissingError()
        return JoinTokenDTO(token=self._tokens.generate(room, username, config))
