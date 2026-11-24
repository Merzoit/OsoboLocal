from __future__ import annotations

import pytest
from app.db.models import Category
from app.ids import new_uuid
from app.timeutil import utcnow
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def test_pragmas_are_set(db: Session) -> None:
    conn = db.connection()
    assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    assert conn.execute(text("PRAGMA synchronous")).scalar() == 2  # FULL
    journal = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert str(journal).lower() == "wal"
    # busy_timeout is in milliseconds
    assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_foreign_keys_enforced(db: Session) -> None:
    now = utcnow()
    orphan = Category(
        id=new_uuid(),
        name="orphan-parent-ok",
        sort_order=0,
        active=True,
        version=1,
        revision=0,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(orphan)
    db.flush()

    from app.db.models import MenuItem

    bad = MenuItem(
        id=new_uuid(),
        category_id=new_uuid(),  # nonexistent
        name="bad",
        description=None,
        price=100,
        image_path=None,
        active=True,
        available_from=None,
        available_to=None,
        updated_by=None,
        version=1,
        revision=0,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.flush()
