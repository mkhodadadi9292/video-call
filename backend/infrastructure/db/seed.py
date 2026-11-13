"""Startup seeding: tables, admin user, Jitsi credentials. Idempotent."""

import secrets

from backend.config import Settings
from backend.infrastructure.auth.passwords import hash_password
from backend.infrastructure.db.database import Database
from backend.infrastructure.db.models import JitsiConfig, User

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345@mn"


def seed_database(database: Database, settings: Settings) -> None:
    database.create_all()
    with database.session() as session:
        if not session.query(User).filter(User.username == ADMIN_USERNAME).first():
            session.add(
                User(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(ADMIN_PASSWORD),
                    role="admin",
                )
            )
        if not session.query(JitsiConfig).first():
            session.add(
                JitsiConfig(
                    app_id=settings.jitsi_jwt_app_id,
                    app_secret=settings.jitsi_jwt_secret or secrets.token_urlsafe(32),
                )
            )
        session.commit()
