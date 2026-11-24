from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Generator
from typing import Annotated, Any

from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Device, IdempotencyKey
from app.errors import AppError
from app.security import sha256_hex
from app.timeutil import utcnow


def get_db(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_device(
    request: Request,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> Device:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("unauthorized", "Missing or invalid Authorization header", status_code=401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AppError("unauthorized", "Missing device token", status_code=401)

    token_hash = sha256_hex(token)
    device = db.execute(
        select(Device).where(
            Device.token_hash == token_hash,
            Device.active.is_(True),
            Device.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if device is None:
        raise AppError("unauthorized", "Invalid device token", status_code=401)

    device.last_seen_at = utcnow()
    request.state.device = device
    return device


CurrentDevice = Annotated[Device, Depends(get_current_device)]


def require_roles(*roles: str) -> Callable[..., Device]:
    allowed = frozenset(roles)

    def _dependency(device: CurrentDevice) -> Device:
        if device.role not in allowed:
            raise AppError(
                "forbidden",
                "Device role is not allowed for this endpoint",
                status_code=403,
                details={"role": device.role, "allowed": sorted(allowed)},
            )
        return device

    return _dependency


def _canonical_body_hash(body: bytes) -> str:
    if not body:
        return sha256_hex("")
    try:
        parsed = json.loads(body)
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256_hex(canonical)
    except json.JSONDecodeError:
        return hashlib.sha256(body).hexdigest()


async def require_idempotency_key(
    request: Request,
    db: DbSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> uuid.UUID | None:
    """Enforce Idempotency-Key for mutating endpoints.

    Do not attach this to ``POST /devices/register``: a cached response would
    persist the plaintext device token.

    Returns ``None`` when a replay response was placed on ``request.state.idempotency_replay``.
    Returns the key UUID when the request should proceed and later be stored.
    """
    if not idempotency_key:
        raise AppError("validation_error", "Idempotency-Key header is required", status_code=422)

    try:
        key = uuid.UUID(idempotency_key)
    except ValueError as exc:
        raise AppError(
            "validation_error",
            "Idempotency-Key must be a UUID",
            status_code=422,
        ) from exc

    body = await request.body()
    request_hash = _canonical_body_hash(body)
    endpoint = f"{request.method} {request.url.path}"

    existing = db.get(IdempotencyKey, key)
    if existing is not None:
        if existing.endpoint != endpoint or existing.request_hash != request_hash:
            raise AppError(
                "idempotency_conflict",
                "Idempotency-Key was reused with a different request body",
                status_code=422,
            )
        request.state.idempotency_replay = JSONResponse(
            status_code=existing.response_status,
            content=existing.response_body,
        )
        return None

    request.state.idempotency_key = key
    request.state.idempotency_endpoint = endpoint
    request.state.idempotency_request_hash = request_hash
    return key


def store_idempotent_response(
    request: Request,
    db: Session,
    *,
    status_code: int,
    body: Any,
) -> None:
    key = getattr(request.state, "idempotency_key", None)
    if key is None:
        return
    if db.get(IdempotencyKey, key) is not None:
        return

    db.add(
        IdempotencyKey(
            key=key,
            endpoint=request.state.idempotency_endpoint,
            request_hash=request.state.idempotency_request_hash,
            response_status=status_code,
            response_body=body,
            created_at=utcnow(),
        )
    )
    db.flush()
