from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.api import devices, health, menu
from app.api.deps import DbSession, require_idempotency_key, store_idempotent_response
from app.api.devices import get_register_limiter
from app.db.models import Device, DeviceRegistrationCode
from app.db.session import _configure_sqlite, _do_begin
from app.errors import register_exception_handlers
from app.ids import new_uuid
from app.security import generate_device_token, sha256_hex
from app.timeutil import utcnow
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from scripts.seed import seed
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def engine(db_path: Path):
    url = f"sqlite:///{db_path}"
    eng = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(eng, "connect", _configure_sqlite)
    event.listen(eng, "begin", _do_begin)

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return eng


@pytest.fixture()
def session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def db(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture()
def app(session_factory: sessionmaker[Session], engine) -> FastAPI:
    application = FastAPI()
    register_exception_handlers(application)
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.terminal_status = "mock"
    application.state.sync_status = "not_configured"
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(devices.router, prefix="/api/v1")
    application.include_router(menu.router, prefix="/api/v1")

    @application.post("/api/v1/_test/idempotent")
    async def idempotent_echo(
        request: Request,
        db: DbSession,
        payload: dict,
        _key: uuid.UUID | None = Depends(require_idempotency_key),
    ):
        replay = getattr(request.state, "idempotency_replay", None)
        if replay is not None:
            return replay
        body = {"ok": True, "echo": payload}
        store_idempotent_response(request, db, status_code=200, body=body)
        return body

    get_register_limiter().reset()
    return application


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_db(session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    with session_factory() as session:
        seed(session)
        session.commit()
    return session_factory


def create_registration_code(
    session: Session,
    *,
    role: str = "kiosk",
    station_id: uuid.UUID | None = None,
    code: str | None = None,
) -> str:
    plaintext = code or f"test-code-{uuid.uuid4()}"
    now = utcnow()
    session.add(
        DeviceRegistrationCode(
            id=new_uuid(),
            code_hash=sha256_hex(plaintext),
            role=role,
            station_id=station_id,
            expires_at=now + timedelta(hours=1),
            used_at=None,
            created_at=now,
        )
    )
    session.flush()
    return plaintext


def create_device(
    session: Session,
    *,
    role: str = "kiosk",
    station_id: uuid.UUID | None = None,
) -> tuple[Device, str]:
    token = generate_device_token()
    now = utcnow()
    device = Device(
        id=new_uuid(),
        name=f"{role}-device",
        role=role,
        station_id=station_id,
        token_hash=sha256_hex(token),
        app_version="test",
        last_seen_at=now,
        active=True,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    session.add(device)
    session.flush()
    return device, token
