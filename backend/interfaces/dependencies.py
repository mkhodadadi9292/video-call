"""FastAPI dependencies: DB sessions, container access, stub auth."""

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.domain.entities import UserAccount
from backend.interfaces.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_db(request: Request):
    """One SQLAlchemy session per request, closed afterwards."""
    with request.app.state.database.session() as session:
        yield session


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
    container: Container = Depends(get_container),
) -> UserAccount:
    """Required auth — 401 unless a valid stub token is presented."""
    account = container.authenticator(db).authenticate(authorization)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return account
