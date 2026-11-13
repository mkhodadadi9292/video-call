"""SQLAlchemy implementation of the RoomRepository port (Phase 3).

The only place where ORM rows are mapped to domain entities and back.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.domain.entities import ChatMessage, JitsiRoomId, Participant, Room, RoomName
from backend.domain.ports.room_repository import RoomRepository
from backend.infrastructure.db.models import (
    Room as RoomModel,
    RoomMessage as RoomMessageModel,
    RoomParticipant as RoomParticipantModel,
    User,
)


def _room_to_domain(orm: RoomModel) -> Room:
    return Room(
        id=orm.id,
        name=RoomName(orm.name),
        jitsi_room_id=JitsiRoomId(orm.jitsi_room_id),
        created_by=orm.created_by,
        is_active=orm.is_active,
        created_at=orm.created_at,
    )


class SqlAlchemyRoomRepository(RoomRepository):
    def __init__(self, db: Session):
        self._db = db

    # -- rooms ------------------------------------------------------------

    def create_room(self, room: Room) -> Room:
        orm = RoomModel(
            name=room.name.value,
            jitsi_room_id=room.jitsi_room_id.value,
            created_by=room.created_by,
        )
        self._db.add(orm)
        self._db.commit()
        self._db.refresh(orm)
        return _room_to_domain(orm)

    def list_active_rooms(self) -> list[Room]:
        rows = (
            self._db.query(RoomModel)
            .filter(RoomModel.is_active.is_(True))
            .order_by(RoomModel.created_at.desc(), RoomModel.id.desc())
            .all()
        )
        return [_room_to_domain(r) for r in rows]

    def get_room(self, room_id: int) -> Room | None:
        orm = self._db.get(RoomModel, room_id)
        return _room_to_domain(orm) if orm else None

    def close_room(self, room_id: int) -> Room | None:
        orm = self._db.get(RoomModel, room_id)
        if not orm:
            return None
        orm.is_active = False
        self._db.commit()
        self._db.refresh(orm)
        return _room_to_domain(orm)

    # -- participants -----------------------------------------------------

    def add_participant(self, room_id: int, user_id: int) -> None:
        existing = (
            self._db.query(RoomParticipantModel)
            .filter(
                RoomParticipantModel.room_id == room_id,
                RoomParticipantModel.user_id == user_id,
            )
            .first()
        )
        if existing:
            existing.left_at = None  # rejoin
        else:
            self._db.add(RoomParticipantModel(room_id=room_id, user_id=user_id))
        self._db.commit()

    def remove_participant(self, room_id: int, user_id: int) -> None:
        row = (
            self._db.query(RoomParticipantModel)
            .filter(
                RoomParticipantModel.room_id == room_id,
                RoomParticipantModel.user_id == user_id,
                RoomParticipantModel.left_at.is_(None),
            )
            .first()
        )
        if row:
            row.left_at = datetime.now(timezone.utc)
            self._db.commit()

    def list_participants(self, room_id: int) -> list[Participant]:
        rows = (
            self._db.query(RoomParticipantModel, User.username)
            .join(User, RoomParticipantModel.user_id == User.id)
            .filter(RoomParticipantModel.room_id == room_id)
            .order_by(RoomParticipantModel.joined_at.asc(), RoomParticipantModel.id.asc())
            .all()
        )
        return [
            Participant(
                user_id=p.user_id,
                username=username,
                joined_at=p.joined_at,
                left_at=p.left_at,
            )
            for p, username in rows
        ]

    def count_participants(self, room_id: int) -> int:
        return (
            self._db.query(RoomParticipantModel)
            .filter(
                RoomParticipantModel.room_id == room_id,
                RoomParticipantModel.left_at.is_(None),
            )
            .count()
        )

    # -- messages ---------------------------------------------------------

    def add_message(self, room_id: int, user_id: int, text: str) -> ChatMessage:
        # Reuse the domain value object for validation (single source of truth).
        message = ChatMessage(id=None, room_id=room_id, user_id=user_id, username="", text=text)
        orm = RoomMessageModel(room_id=room_id, user_id=user_id, message=message.text)
        self._db.add(orm)
        self._db.commit()
        self._db.refresh(orm)
        return ChatMessage(
            id=orm.id,
            room_id=orm.room_id,
            user_id=orm.user_id,
            username=orm.user.username,
            text=orm.message,
            created_at=orm.created_at,
        )

    def list_messages(self, room_id: int, page: int, size: int) -> list[ChatMessage]:
        base_q = self._db.query(RoomMessageModel).filter(RoomMessageModel.room_id == room_id)
        offset = (page - 1) * size
        rows = (
            base_q.order_by(RoomMessageModel.created_at.desc(), RoomMessageModel.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )
        return [
            ChatMessage(
                id=m.id,
                room_id=m.room_id,
                user_id=m.user_id,
                username=m.user.username,
                text=m.message,
                created_at=m.created_at,
            )
            for m in reversed(rows)  # oldest first for display
        ]
