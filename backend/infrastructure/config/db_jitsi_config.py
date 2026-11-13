"""DB-backed JitsiConfigProvider with env-var override.

Precedence: JITSI_JWT_SECRET env var (used in Docker so backend and prosody
share one secret) → seeded jitsi_config DB row.
"""

from backend.domain.entities import JitsiConfig
from backend.domain.ports.jitsi_config_provider import JitsiConfigProvider
from backend.infrastructure.db.models import JitsiConfig as JitsiConfigModel


class DbJitsiConfigProvider(JitsiConfigProvider):
    def __init__(self, db_session_factory, env_app_id: str | None, env_secret: str | None):
        self._db_session_factory = db_session_factory
        self._env_app_id = env_app_id
        self._env_secret = env_secret

    def get(self) -> JitsiConfig | None:
        if self._env_secret:
            return JitsiConfig(
                app_id=self._env_app_id or "video-call-system",
                app_secret=self._env_secret,
            )
        with self._db_session_factory() as session:
            row = session.query(JitsiConfigModel).first()
            if not row:
                return None
            return JitsiConfig(app_id=row.app_id, app_secret=row.app_secret)
