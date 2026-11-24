from __future__ import annotations

import pytest
from app.db.models import Device
from app.ids import new_uuid
from app.security import sha256_hex
from app.timeutil import utcnow
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def test_device_role_check(db: Session) -> None:
    now = utcnow()
    db.add(
        Device(
            id=new_uuid(),
            name="bad",
            role="admin",  # not allowed on device
            station_id=None,
            token_hash=sha256_hex("t"),
            app_version=None,
            last_seen_at=None,
            active=True,
            version=1,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
