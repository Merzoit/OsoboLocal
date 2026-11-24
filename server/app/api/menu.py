from __future__ import annotations

import uuid
from datetime import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, require_roles
from app.db.menu_revision import get_menu_revision
from app.db.models import (
    Category,
    ItemStation,
    MenuItem,
    MenuItemModifierGroup,
    Modifier,
    ModifierGroup,
    Station,
)

router = APIRouter(tags=["menu"])


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int
    active: bool
    revision: int
    version: int
    deleted_at: str | None


class MenuItemOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    price: int
    image_path: str | None
    active: bool
    available_from: time | None
    available_to: time | None
    modifier_group_ids: list[uuid.UUID]
    revision: int
    version: int
    deleted_at: str | None


class ModifierOut(BaseModel):
    id: uuid.UUID
    name: str
    price_delta: int
    active: bool
    revision: int
    version: int
    deleted_at: str | None


class ModifierGroupOut(BaseModel):
    id: uuid.UUID
    name: str
    min_select: int
    max_select: int
    revision: int
    version: int
    deleted_at: str | None
    modifiers: list[ModifierOut]


class ItemStationOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    station_id: uuid.UUID
    station_code: str
    step_name: str
    prep_seconds: int
    revision: int
    version: int
    deleted_at: str | None


class MenuResponse(BaseModel):
    revision: int
    categories: list[CategoryOut]
    items: list[MenuItemOut]
    modifier_groups: list[ModifierGroupOut]
    item_stations: list[ItemStationOut]


def _iso(dt: Any) -> str | None:
    return dt.isoformat() if dt is not None else None


@router.get("/menu", response_model=MenuResponse)
def get_menu(
    db: DbSession,
    _device: Annotated[Any, Depends(require_roles("kiosk", "operator"))],
    since: Annotated[int | None, Query(ge=0)] = None,
) -> MenuResponse:
    current = get_menu_revision(db)
    since_val = since if since is not None else -1

    categories = db.execute(
        select(Category)
        .where(Category.revision > since_val)
        .order_by(Category.sort_order, Category.name)
    ).scalars().all()

    items = db.execute(
        select(MenuItem).where(MenuItem.revision > since_val).order_by(MenuItem.name)
    ).scalars().all()

    groups = db.execute(
        select(ModifierGroup).where(ModifierGroup.revision > since_val).order_by(ModifierGroup.name)
    ).scalars().all()

    item_stations = db.execute(
        select(ItemStation, Station)
        .join(Station, Station.id == ItemStation.station_id)
        .where(ItemStation.revision > since_val)
        .order_by(ItemStation.item_id, ItemStation.step_name)
    ).all()

    item_ids = [item.id for item in items]
    links: dict[uuid.UUID, list[uuid.UUID]] = {item_id: [] for item_id in item_ids}
    if item_ids:
        rows = db.execute(
            select(MenuItemModifierGroup).where(MenuItemModifierGroup.item_id.in_(item_ids))
        ).scalars().all()
        for row in rows:
            links.setdefault(row.item_id, []).append(row.group_id)

    modifiers_by_group: dict[uuid.UUID, list[Modifier]] = {}
    if groups:
        group_ids = [g.id for g in groups]
        mods = db.execute(
            select(Modifier).where(Modifier.group_id.in_(group_ids)).order_by(Modifier.name)
        ).scalars().all()
        for mod in mods:
            modifiers_by_group.setdefault(mod.group_id, []).append(mod)

    return MenuResponse(
        revision=current,
        categories=[
            CategoryOut(
                id=c.id,
                name=c.name,
                sort_order=c.sort_order,
                active=c.active,
                revision=c.revision,
                version=c.version,
                deleted_at=_iso(c.deleted_at),
            )
            for c in categories
        ],
        items=[
            MenuItemOut(
                id=i.id,
                category_id=i.category_id,
                name=i.name,
                description=i.description,
                price=i.price,
                image_path=i.image_path,
                active=i.active,
                available_from=i.available_from,
                available_to=i.available_to,
                modifier_group_ids=links.get(i.id, []),
                revision=i.revision,
                version=i.version,
                deleted_at=_iso(i.deleted_at),
            )
            for i in items
        ],
        modifier_groups=[
            ModifierGroupOut(
                id=g.id,
                name=g.name,
                min_select=g.min_select,
                max_select=g.max_select,
                revision=g.revision,
                version=g.version,
                deleted_at=_iso(g.deleted_at),
                modifiers=[
                    ModifierOut(
                        id=m.id,
                        name=m.name,
                        price_delta=m.price_delta,
                        active=m.active,
                        revision=m.revision,
                        version=m.version,
                        deleted_at=_iso(m.deleted_at),
                    )
                    for m in modifiers_by_group.get(g.id, [])
                ],
            )
            for g in groups
        ],
        item_stations=[
            ItemStationOut(
                id=is_.id,
                item_id=is_.item_id,
                station_id=is_.station_id,
                station_code=station.code,
                step_name=is_.step_name,
                prep_seconds=is_.prep_seconds,
                revision=is_.revision,
                version=is_.version,
                deleted_at=_iso(is_.deleted_at),
            )
            for is_, station in item_stations
        ],
    )
