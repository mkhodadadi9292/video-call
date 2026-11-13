"""PyJWT implementation of the RoomTokenGenerator port.

Produces the JWT that self-hosted Jitsi (prosody token_verification module)
validates at join time:
  aud=jitsi, iss=<app_id>, sub=meet.jitsi, room=<jitsi_room_id>,
  context.user.name=<username>, exp/iat.
"""

from datetime import datetime, timedelta, timezone

import jwt

from backend.domain.entities import JitsiConfig, Room
from backend.domain.ports.token_generator import RoomTokenGenerator


class JwtRoomTokenGenerator(RoomTokenGenerator):
    def __init__(self, expire_minutes: int):
        self._expire_minutes = expire_minutes

    def generate(self, room: Room, username: str, config: JitsiConfig) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "aud": "jitsi",
            "iss": config.app_id,
            "sub": "meet.jitsi",
            "room": room.jitsi_room_id.value,
            "exp": now + timedelta(minutes=self._expire_minutes),
            "iat": now,
            "context": {"user": {"name": username}},
        }
        return jwt.encode(payload, config.app_secret, algorithm="HS256")
