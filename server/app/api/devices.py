from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.rate_limit import SlidingWindowRateLimiter
from app.config import get_settings
from app.db.models import Device, DeviceRegistrationCode
from app.errors import AppError
from app.ids import new_uuid
from app.security import generate_device_token, sha256_hex
from app.timeutil import utcnow

router = APIRouter(prefix="/devices", tags=["devices"])

DeviceRole = Literal["kiosk", "station", "expo", "operator"]

_register_limiter: SlidingWindowRateLimiter | None = None


def get_register_limiter() -> SlidingWindowRateLimiter:
    global _register_limiter
    if _register_limiter is None:
        settings = get_settings()
        _register_limiter = SlidingWindowRateLimiter(
            limit=settings.register_rate_limit,
            window_seconds=settings.register_rate_window_seconds,
        )
    return _register_limiter


class RegisterRequest(BaseModel):
    code: str = Field(min_length=1)
    role: DeviceRole
    name: str | None = None
    app_version: str | None = None


class RegisterResponse(BaseModel):
    device_id: uuid.UUID
    token: str
    role: DeviceRole


@router.post("/register", response_model=RegisterResponse)
def register_device(
    payload: RegisterRequest,
    request: Request,
    db: DbSession,
) -> RegisterResponse:
    client_key = request.client.host if request.client else "unknown"
    if not get_register_limiter().allow(client_key):
        raise AppError(
            "rate_limited",
            "Too many registration attempts",
            status_code=429,
        )

    now = utcnow()
    code_hash = sha256_hex(payload.code)
    reg = db.execute(
        select(DeviceRegistrationCode).where(
            DeviceRegistrationCode.code_hash == code_hash,
        )
    ).scalar_one_or_none()

    if reg is None:
        raise AppError("invalid_code", "Registration code is invalid", status_code=400)
    if reg.used_at is not None:
        raise AppError("code_used", "Registration code already used", status_code=400)
    if reg.expires_at <= now:
        raise AppError("code_expired", "Registration code expired", status_code=400)
    if reg.role != payload.role:
        raise AppError(
            "role_mismatch",
            "Requested role does not match registration code",
            status_code=400,
            details={"expected": reg.role},
        )

    token = generate_device_token()
    device = Device(
        id=new_uuid(),
        name=payload.name,
        role=reg.role,
        station_id=reg.station_id,
        token_hash=sha256_hex(token),
        app_version=payload.app_version,
        last_seen_at=now,
        active=True,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    reg.used_at = now
    db.add(device)
    db.flush()

    return RegisterResponse(device_id=device.id, token=token, role=device.role)  # type: ignore[arg-type]
