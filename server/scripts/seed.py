"""Load demo menu data. Safe to re-run: uses fixed UUIDs and upserts."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

# Allow `python scripts/seed.py` from server/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.db.menu_revision import bump_menu_revision, get_menu_revision
from app.db.migrate import upgrade_head
from app.db.models import (
    Category,
    ItemStation,
    MenuItem,
    MenuItemModifierGroup,
    Modifier,
    ModifierGroup,
    Station,
    SyncState,
)
from app.db.session import create_engine_from_url, get_session_factory, session_scope
from app.timeutil import utcnow
from sqlalchemy import select

# Fixed demo IDs so re-seeding is idempotent.
STATION_KITCHEN = uuid.UUID("01900000-0000-7000-8000-000000000001")
STATION_GRILL = uuid.UUID("01900000-0000-7000-8000-000000000002")
STATION_COLD = uuid.UUID("01900000-0000-7000-8000-000000000003")

CAT_MAINS = uuid.UUID("01900000-0000-7000-8000-000000000101")
CAT_SIDES = uuid.UUID("01900000-0000-7000-8000-000000000102")
CAT_DRINKS = uuid.UUID("01900000-0000-7000-8000-000000000103")
CAT_DESSERTS = uuid.UUID("01900000-0000-7000-8000-000000000104")

MG_DONENESS = uuid.UUID("01900000-0000-7000-8000-000000000201")
MOD_RARE = uuid.UUID("01900000-0000-7000-8000-000000000211")
MOD_MEDIUM = uuid.UUID("01900000-0000-7000-8000-000000000212")
MOD_WELL = uuid.UUID("01900000-0000-7000-8000-000000000213")

ITEM_STEAK = uuid.UUID("01900000-0000-7000-8000-000000000301")
ITEM_BURGER = uuid.UUID("01900000-0000-7000-8000-000000000302")
ITEM_PASTA = uuid.UUID("01900000-0000-7000-8000-000000000303")
ITEM_SALAD = uuid.UUID("01900000-0000-7000-8000-000000000304")
ITEM_SOUP = uuid.UUID("01900000-0000-7000-8000-000000000305")
ITEM_FRIES = uuid.UUID("01900000-0000-7000-8000-000000000306")
ITEM_COLA = uuid.UUID("01900000-0000-7000-8000-000000000307")
ITEM_WATER = uuid.UUID("01900000-0000-7000-8000-000000000308")
ITEM_CAKE = uuid.UUID("01900000-0000-7000-8000-000000000309")
ITEM_RIBS = uuid.UUID("01900000-0000-7000-8000-000000000310")


def _upsert(session, model, pk, defaults: dict) -> object:
    row = session.get(model, pk)
    if row is None:
        row = model(id=pk, **defaults)
        session.add(row)
    else:
        for key, value in defaults.items():
            setattr(row, key, value)
    return row


def seed(session) -> None:
    now = utcnow()
    existing = get_menu_revision(session)
    # On first seed, bump once and stamp everything with the same revision.
    # On re-run, keep existing revisions (idempotent content update without churn).
    if existing == 0:
        revision = bump_menu_revision(session)
    else:
        revision = existing

    syncable = dict(version=1, created_at=now, updated_at=now, deleted_at=None)

    _upsert(
        session,
        Station,
        STATION_KITCHEN,
        {"code": "kitchen", "name": "Кухня", "capacity": 1, "active": True, **syncable},
    )
    _upsert(
        session,
        Station,
        STATION_GRILL,
        {"code": "grill", "name": "Гриль", "capacity": 2, "active": True, **syncable},
    )
    _upsert(
        session,
        Station,
        STATION_COLD,
        {"code": "cold", "name": "Закуски", "capacity": 1, "active": True, **syncable},
    )

    menu_sync = {**syncable, "revision": revision}

    _upsert(
        session,
        Category,
        CAT_MAINS,
        {"name": "Основные", "sort_order": 1, "active": True, **menu_sync},
    )
    _upsert(
        session,
        Category,
        CAT_SIDES,
        {"name": "Гарниры", "sort_order": 2, "active": True, **menu_sync},
    )
    _upsert(
        session,
        Category,
        CAT_DRINKS,
        {"name": "Напитки", "sort_order": 3, "active": True, **menu_sync},
    )
    _upsert(
        session,
        Category,
        CAT_DESSERTS,
        {"name": "Десерты", "sort_order": 4, "active": True, **menu_sync},
    )

    _upsert(
        session,
        ModifierGroup,
        MG_DONENESS,
        {"name": "Прожарка", "min_select": 1, "max_select": 1, **menu_sync},
    )
    for mod_id, name in (
        (MOD_RARE, "Rare"),
        (MOD_MEDIUM, "Medium"),
        (MOD_WELL, "Well done"),
    ):
        _upsert(
            session,
            Modifier,
            mod_id,
            {
                "group_id": MG_DONENESS,
                "name": name,
                "price_delta": 0,
                "active": True,
                **menu_sync,
            },
        )

    items = [
        (ITEM_STEAK, CAT_MAINS, "Стейк с картофелем и соусом", 2450, "Рибай, гарнир и соус"),
        (ITEM_BURGER, CAT_MAINS, "Бургер", 1290, None),
        (ITEM_PASTA, CAT_MAINS, "Паста карбонара", 990, None),
        (ITEM_SALAD, CAT_MAINS, "Цезарь", 790, None),
        (ITEM_SOUP, CAT_MAINS, "Томатный суп", 450, None),
        (ITEM_FRIES, CAT_SIDES, "Картофель фри", 350, None),
        (ITEM_COLA, CAT_DRINKS, "Кола", 250, None),
        (ITEM_WATER, CAT_DRINKS, "Вода", 150, None),
        (ITEM_CAKE, CAT_DESSERTS, "Чизкейк", 520, None),
        (ITEM_RIBS, CAT_MAINS, "Рёбра BBQ", 1890, None),
    ]
    for item_id, cat_id, name, price, description in items:
        _upsert(
            session,
            MenuItem,
            item_id,
            {
                "category_id": cat_id,
                "name": name,
                "description": description,
                "price": price,
                "image_path": None,
                "active": True,
                "available_from": None,
                "available_to": None,
                "updated_by": None,
                **menu_sync,
            },
        )

    # Multi-station steak: grill 720s, kitchen 360s, cold 120s
    def _sid(n: int) -> uuid.UUID:
        return uuid.UUID(f"01900000-0000-7000-8000-0000000004{n:02d}")

    station_steps = [
        (_sid(1), ITEM_STEAK, STATION_GRILL, "Стейк", 720),
        (_sid(2), ITEM_STEAK, STATION_KITCHEN, "Гарнир", 360),
        (_sid(3), ITEM_STEAK, STATION_COLD, "Соус", 120),
        (_sid(4), ITEM_BURGER, STATION_GRILL, "Котлета", 480),
        (_sid(5), ITEM_BURGER, STATION_KITCHEN, "Сборка", 180),
        (_sid(6), ITEM_PASTA, STATION_KITCHEN, "Паста", 600),
        (_sid(7), ITEM_SALAD, STATION_COLD, "Салат", 300),
        (_sid(8), ITEM_SOUP, STATION_KITCHEN, "Суп", 240),
        (_sid(9), ITEM_FRIES, STATION_KITCHEN, "Фри", 300),
        (_sid(10), ITEM_RIBS, STATION_GRILL, "Рёбра", 900),
        (_sid(11), ITEM_RIBS, STATION_KITCHEN, "Гарнир", 300),
        (_sid(12), ITEM_CAKE, STATION_COLD, "Десерт", 60),
    ]
    for sid, item_id, station_id, step_name, prep in station_steps:
        _upsert(
            session,
            ItemStation,
            sid,
            {
                "item_id": item_id,
                "station_id": station_id,
                "step_name": step_name,
                "prep_seconds": prep,
                **menu_sync,
            },
        )

    # Drinks have no station prep in demo — skip.

    link = session.execute(
        select(MenuItemModifierGroup).where(
            MenuItemModifierGroup.item_id == ITEM_STEAK,
            MenuItemModifierGroup.group_id == MG_DONENESS,
        )
    ).scalar_one_or_none()
    if link is None:
        session.add(MenuItemModifierGroup(item_id=ITEM_STEAK, group_id=MG_DONENESS))

    link2 = session.execute(
        select(MenuItemModifierGroup).where(
            MenuItemModifierGroup.item_id == ITEM_RIBS,
            MenuItemModifierGroup.group_id == MG_DONENESS,
        )
    ).scalar_one_or_none()
    if link2 is None:
        session.add(MenuItemModifierGroup(item_id=ITEM_RIBS, group_id=MG_DONENESS))

    # Ensure counter row exists even if seed was partial.
    if session.get(SyncState, "menu_revision") is None:
        session.add(SyncState(key="menu_revision", value=str(revision), updated_at=now))


def main() -> None:
    settings = get_settings()
    Path("data").mkdir(exist_ok=True)
    upgrade_head(settings.database_url)
    engine = create_engine_from_url(settings.database_url)
    factory = get_session_factory(engine)
    with session_scope(factory) as session:
        seed(session)
    print("Seed completed")


if __name__ == "__main__":
    main()
