"""Application-level errors.

Raised by use cases; mapped to HTTP responses by the interfaces layer.
The application layer never imports FastAPI/HTTPException — that coupling
would break the dependency rule (HTTP is an outer-layer concern).
"""


class ApplicationError(Exception):
    """Base class for all application errors."""


class RoomNotFoundError(ApplicationError):
    def __init__(self, room_id: int):
        super().__init__(f"Room {room_id} not found")
        self.room_id = room_id


class RoomInactiveError(ApplicationError):
    def __init__(self, room_id: int):
        super().__init__(f"Room {room_id} is not active")
        self.room_id = room_id


class JitsiConfigMissingError(ApplicationError):
    def __init__(self):
        super().__init__("Jitsi configuration is missing")


class InvalidCredentialsError(ApplicationError):
    def __init__(self):
        super().__init__("Invalid username or password")
