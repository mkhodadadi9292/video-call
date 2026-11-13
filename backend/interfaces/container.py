"""Composition root: wires use cases to their infrastructure adapters.

The only place in the codebase where concrete infrastructure classes are
instantiated. Everything else depends on ports (domain/ports) or DTOs.
"""

from backend.application.use_cases.auth import LoginUseCase
from backend.application.use_cases.chat import ListMessagesUseCase, SendMessageUseCase
from backend.application.use_cases.participation import (
    JoinRoomUseCase,
    LeaveRoomUseCase,
    ListParticipantsUseCase,
)
from backend.application.use_cases.room_lifecycle import (
    CreateRoomUseCase,
    EndRoomUseCase,
    GetRoomUseCase,
    ListRoomsUseCase,
)
from backend.application.use_cases.token import GenerateJoinTokenUseCase
from backend.config import Settings
from backend.infrastructure.auth.jwt_token_generator import JwtRoomTokenGenerator
from backend.infrastructure.auth.passwords import Pbkdf2PasswordHasher
from backend.infrastructure.auth.stub_authenticator import StubAuthenticator
from backend.infrastructure.config.db_jitsi_config import DbJitsiConfigProvider
from backend.infrastructure.db.database import Database
from backend.infrastructure.db.room_repository import SqlAlchemyRoomRepository
from backend.infrastructure.db.user_repository import SqlAlchemyUserRepository


class Container:
    def __init__(self, database: Database, settings: Settings):
        self.database = database
        self.settings = settings

    # -- driven adapters (implement domain ports) -------------------------

    def rooms_repository(self, session) -> SqlAlchemyRoomRepository:
        return SqlAlchemyRoomRepository(session)

    def users_repository(self, session) -> SqlAlchemyUserRepository:
        return SqlAlchemyUserRepository(session)

    def password_hasher(self) -> Pbkdf2PasswordHasher:
        return Pbkdf2PasswordHasher()

    def token_generator(self) -> JwtRoomTokenGenerator:
        return JwtRoomTokenGenerator(self.settings.jitsi_jwt_expire_minutes)

    def jitsi_config_provider(self) -> DbJitsiConfigProvider:
        return DbJitsiConfigProvider(
            self.database.session_factory,
            self.settings.jitsi_jwt_app_id,
            self.settings.jitsi_jwt_secret,
        )

    def authenticator(self, session) -> StubAuthenticator:
        return StubAuthenticator(self.users_repository(session))

    # -- use cases ---------------------------------------------------------

    def login(self, session) -> LoginUseCase:
        return LoginUseCase(self.users_repository(session), self.password_hasher())

    def create_room(self, session) -> CreateRoomUseCase:
        return CreateRoomUseCase(self.rooms_repository(session))

    def list_rooms(self, session) -> ListRoomsUseCase:
        return ListRoomsUseCase(self.rooms_repository(session))

    def get_room(self, session) -> GetRoomUseCase:
        return GetRoomUseCase(self.rooms_repository(session))

    def end_room(self, session) -> EndRoomUseCase:
        return EndRoomUseCase(self.rooms_repository(session))

    def join_room(self, session) -> JoinRoomUseCase:
        return JoinRoomUseCase(self.rooms_repository(session))

    def leave_room(self, session) -> LeaveRoomUseCase:
        return LeaveRoomUseCase(self.rooms_repository(session))

    def list_participants(self, session) -> ListParticipantsUseCase:
        return ListParticipantsUseCase(self.rooms_repository(session))

    def send_message(self, session) -> SendMessageUseCase:
        return SendMessageUseCase(self.rooms_repository(session))

    def list_messages(self, session) -> ListMessagesUseCase:
        return ListMessagesUseCase(self.rooms_repository(session))

    def generate_token(self, session) -> GenerateJoinTokenUseCase:
        return GenerateJoinTokenUseCase(
            self.rooms_repository(session),
            self.token_generator(),
            self.jitsi_config_provider(),
        )
