"""Application factory.

`create_app(database, settings)` builds the FastAPI app, seeds the database
(idempotent), wires the composition root, and maps application errors to
HTTP responses. The module-level `app` is the uvicorn entry point
(`uvicorn backend.main:app`).
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.application.errors import (
    ApplicationError,
    InvalidCredentialsError,
    JitsiConfigMissingError,
    RoomInactiveError,
    RoomNotFoundError,
)
from backend.config import Settings
from backend.infrastructure.db.database import Database
from backend.infrastructure.db.seed import seed_database
from backend.interfaces.container import Container
from backend.interfaces.routers.auth import router as auth_router
from backend.interfaces.routers.rooms import router as rooms_router


def create_app(database: Database, settings: Settings) -> FastAPI:
    seed_database(database, settings)

    app = FastAPI(
        title="video-call-system",
        description="Self-hosted video call system (lite-DDD, SOLID, TDD)",
    )
    app.state.database = database
    app.state.container = Container(database, settings)

    app.include_router(auth_router)
    app.include_router(rooms_router)

    # Application errors → HTTP. Keeps routers free of try/except blocks.
    @app.exception_handler(RoomNotFoundError)
    def _room_not_found(_request, exc: RoomNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RoomInactiveError)
    def _room_inactive(_request, exc: RoomInactiveError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialsError)
    def _invalid_credentials(_request, exc: InvalidCredentialsError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(JitsiConfigMissingError)
    def _config_missing(_request, exc: JitsiConfigMissingError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(ApplicationError)
    def _application_error(_request, exc: ApplicationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    def _validation_error(_request, exc: ValueError):
        # Domain value-object validation (RoomName, ChatMessage)
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok"}

    return app


settings = Settings.from_env()
app = create_app(Database(settings.database_url), settings)
