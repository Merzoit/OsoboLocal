from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import devices, health, menu
from app.config import get_settings
from app.db.migrate import upgrade_head
from app.db.session import create_engine_from_url, get_session_factory
from app.errors import register_exception_handlers
from app.logging import setup_logging


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path in {":memory:", ""} or raw_path.startswith("file:"):
        return
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    _ensure_sqlite_parent(settings.database_url)

    if settings.auto_migrate:
        upgrade_head(settings.database_url)

    engine = create_engine_from_url(settings.database_url, echo=settings.debug)
    app.state.engine = engine
    app.state.session_factory = get_session_factory(engine)
    # Stage-1 stubs for health checks
    app.state.terminal_status = "not_configured"
    app.state.sync_status = "not_configured"
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ososbo Local Server",
        version=settings.app_version,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(menu.router, prefix="/api/v1")
    return app


app = create_app()
