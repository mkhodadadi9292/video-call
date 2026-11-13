"""SQLAlchemy implementation of the UserRepository port."""

from sqlalchemy.orm import Session

from backend.domain.entities import UserAccount
from backend.domain.ports.user_repository import UserRepository
from backend.infrastructure.db.models import User


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _to_domain(user: User) -> UserAccount:
        return UserAccount(
            id=user.id, username=user.username, role=user.role, password_hash=user.password_hash
        )

    def get_by_username(self, username: str) -> UserAccount | None:
        user = self._db.query(User).filter(User.username == username).first()
        return self._to_domain(user) if user else None

    def create(self, username: str, password_hash: str, role: str) -> UserAccount:
        user = User(username=username, password_hash=password_hash, role=role)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return self._to_domain(user)
