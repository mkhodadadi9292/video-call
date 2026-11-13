"""Environment-driven settings (outermost configuration concern)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    jitsi_jwt_app_id: str
    jitsi_jwt_secret: str | None
    jitsi_jwt_expire_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./video_call.db"),
            jitsi_jwt_app_id=os.environ.get("JITSI_JWT_APP_ID", "video-call-system"),
            jitsi_jwt_secret=os.environ.get("JITSI_JWT_SECRET") or None,
            jitsi_jwt_expire_minutes=int(os.environ.get("JITSI_JWT_EXPIRE_MINUTES", "1440")),
        )
