from __future__ import annotations

from app.db.menu_revision import get_menu_revision
from app.db.models import MenuItem
from app.timeutil import utcnow
from fastapi.testclient import TestClient
from scripts.seed import ITEM_STEAK, seed
from sqlalchemy.orm import Session, sessionmaker
from tests.conftest import create_device


def test_menu_full_and_since(client: TestClient, db: Session, seeded_db: sessionmaker) -> None:
    _, token = create_device(db, role="kiosk")
    db.commit()
    headers = {"Authorization": f"Bearer {token}"}

    full = client.get("/api/v1/menu", headers=headers)
    assert full.status_code == 200
    data = full.json()
    assert data["revision"] >= 1
    assert len(data["categories"]) >= 3
    assert len(data["items"]) >= 8
    assert any(i["name"].startswith("Стейк") for i in data["items"])
    steak_stations = [s for s in data["item_stations"] if s["item_id"] == str(ITEM_STEAK)]
    assert len(steak_stations) == 3
    assert any(g["name"] == "Прожарка" for g in data["modifier_groups"])

    revision = data["revision"]
    empty = client.get(f"/api/v1/menu?since={revision}", headers=headers)
    assert empty.status_code == 200
    empty_data = empty.json()
    assert empty_data["revision"] == revision
    assert empty_data["categories"] == []
    assert empty_data["items"] == []
    assert empty_data["modifier_groups"] == []
    assert empty_data["item_stations"] == []


def test_menu_since_includes_soft_deleted(
    client: TestClient, db: Session, seeded_db: sessionmaker
) -> None:
    _, token = create_device(db, role="operator")
    before = get_menu_revision(db)

    item = db.get(MenuItem, ITEM_STEAK)
    assert item is not None
    from app.db.menu_writes import stamp_menu_entity

    item.deleted_at = utcnow()
    stamp_menu_entity(db, item)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/api/v1/menu?since={before}", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    steak = next(i for i in items if i["id"] == str(ITEM_STEAK))
    assert steak["deleted_at"] is not None


def test_seed_idempotent(session_factory: sessionmaker) -> None:
    with session_factory() as session:
        seed(session)
        session.commit()
    with session_factory() as session:
        seed(session)
        session.commit()
        from app.db.models import Category, MenuItem, Station
        from sqlalchemy import func, select

        assert session.execute(select(func.count()).select_from(Station)).scalar() == 3
        assert session.execute(select(func.count()).select_from(Category)).scalar() == 4
        assert session.execute(select(func.count()).select_from(MenuItem)).scalar() == 10
