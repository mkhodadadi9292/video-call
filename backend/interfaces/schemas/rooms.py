"""Pydantic schemas for room endpoints (HTTP view of application DTOs)."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.application.dto import MessageDTO, ParticipantDTO, RoomDTO, RoomDetailDTO


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class RoomResponse(BaseModel):
    id: int
    name: str
    jitsi_room_id: str
    created_by: int
    is_active: bool
    created_at: datetime | None
    participant_count: int = 0

    @classmethod
    def from_dto(cls, dto: RoomDTO) -> "RoomResponse":
        return cls(
            id=dto.id,
            name=dto.name,
            jitsi_room_id=dto.jitsi_room_id,
            created_by=dto.created_by,
            is_active=dto.is_active,
            created_at=dto.created_at,
            participant_count=dto.participant_count,
        )


class RoomListResponse(BaseModel):
    items: list[RoomResponse]


class ParticipantResponse(BaseModel):
    user_id: int
    username: str
    joined_at: datetime | None
    left_at: datetime | None

    @classmethod
    def from_dto(cls, dto: ParticipantDTO) -> "ParticipantResponse":
        return cls(
            user_id=dto.user_id,
            username=dto.username,
            joined_at=dto.joined_at,
            left_at=dto.left_at,
        )


class RoomDetailResponse(BaseModel):
    id: int
    name: str
    jitsi_room_id: str
    created_by: int
    is_active: bool
    created_at: datetime | None
    participants: list[ParticipantResponse]

    @classmethod
    def from_dto(cls, dto: RoomDetailDTO) -> "RoomDetailResponse":
        return cls(
            id=dto.id,
            name=dto.name,
            jitsi_room_id=dto.jitsi_room_id,
            created_by=dto.created_by,
            is_active=dto.is_active,
            created_at=dto.created_at,
            participants=[ParticipantResponse.from_dto(p) for p in dto.participants],
        )


class MessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    room_id: int
    user_id: int
    username: str
    text: str
    created_at: datetime | None

    @classmethod
    def from_dto(cls, dto: MessageDTO) -> "MessageResponse":
        return cls(
            id=dto.id,
            room_id=dto.room_id,
            user_id=dto.user_id,
            username=dto.username,
            text=dto.text,
            created_at=dto.created_at,
        )


class MessageListResponse(BaseModel):
    items: list[MessageResponse]


class RoomTokenResponse(BaseModel):
    token: str
