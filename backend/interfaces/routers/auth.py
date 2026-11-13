"""Auth endpoints (thin HTTP layer — all logic lives in use cases)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.interfaces.container import Container
from backend.interfaces.dependencies import get_container, get_db
from backend.interfaces.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
):
    dto = container.login(db).execute(body.username, body.password)
    return LoginResponse(access_token=dto.access_token, username=dto.username, role=dto.role)
