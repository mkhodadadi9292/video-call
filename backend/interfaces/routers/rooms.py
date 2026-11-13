"""Room endpoints (thin HTTP layer — all logic lives in use cases)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.domain.entities import UserAccount
from backend.interfaces.container import Container
from backend.interfaces.dependencies import get_container, get_current_user, get_db
from backend.interfaces.schemas.rooms import (
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    ParticipantResponse,
    RoomCreate,
    RoomDetailResponse,
    RoomListResponse,
    RoomResponse,
    RoomTokenResponse,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    body: RoomCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.create_room(db).execute(body.name, current_user.id)
    return RoomResponse.from_dto(dto)


@router.get("", response_model=RoomListResponse)
def list_rooms(
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    items = container.list_rooms(db).execute()
    return RoomListResponse(items=[RoomResponse.from_dto(dto) for dto in items])


@router.get("/{room_id}", response_model=RoomDetailResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.get_room(db).execute(room_id)
    return RoomDetailResponse.from_dto(dto)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_room(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    container.end_room(db).execute(room_id)


@router.post("/{room_id}/join", status_code=status.HTTP_204_NO_CONTENT)
def join_room(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    container.join_room(db).execute(room_id, current_user.id)


@router.post("/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_room(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    container.leave_room(db).execute(room_id, current_user.id)


@router.get("/{room_id}/participants", response_model=list[ParticipantResponse])
def get_participants(
    room_id: int,
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    items = container.list_participants(db).execute(room_id)
    return [ParticipantResponse.from_dto(dto) for dto in items]


@router.get("/{room_id}/messages", response_model=MessageListResponse)
def get_messages(
    room_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    items = container.list_messages(db).execute(room_id, page=page, size=size)
    return MessageListResponse(items=[MessageResponse.from_dto(dto) for dto in items])


@router.post("/{room_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def add_message(
    room_id: int,
    body: MessageCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.send_message(db).execute(room_id, current_user.id, body.message)
    return MessageResponse.from_dto(dto)


@router.post("/{room_id}/token", response_model=RoomTokenResponse)
def get_room_token(
    room_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.generate_token(db).execute(room_id, current_user.username)
    return RoomTokenResponse(token=dto.token)
