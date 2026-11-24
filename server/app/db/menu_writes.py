"""Helpers that stamp menu rows with the global revision counter."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.menu_revision import bump_menu_revision
from app.db.models import ItemStation, MenuItem, MenuItemModifierGroup, Modifier, ModifierGroup
from app.timeutil import utcnow


def stamp_menu_entity(session: Session, *entities: object) -> int:
    """Bump global menu revision and assign it to the given entities' ``revision``."""
    revision = bump_menu_revision(session)
    now = utcnow()
    for entity in entities:
        if hasattr(entity, "revision"):
            entity.revision = revision  # type: ignore[attr-defined]
        if hasattr(entity, "updated_at"):
            entity.updated_at = now  # type: ignore[attr-defined]
        if hasattr(entity, "version"):
            entity.version = int(getattr(entity, "version", 0) or 0) + 1
    return revision


def touch_item_station(session: Session, item_station: ItemStation) -> int:
    """Changing item_station updates revision of the station row and the dish."""
    item = session.get(MenuItem, item_station.item_id)
    if item is None:
        raise ValueError("menu_item not found for item_station")
    return stamp_menu_entity(session, item_station, item)


def touch_item_modifier_link(
    session: Session,
    link: MenuItemModifierGroup,
) -> int:
    """Changing menu_item_modifier_group updates revision of the dish."""
    item = session.get(MenuItem, link.item_id)
    if item is None:
        raise ValueError("menu_item not found for modifier link")
    return stamp_menu_entity(session, item)


def touch_modifier(session: Session, modifier: Modifier) -> int:
    """Changing a modifier also bumps its group so clients refetch the group."""
    group = session.get(ModifierGroup, modifier.group_id)
    if group is None:
        raise ValueError("modifier_group not found")
    return stamp_menu_entity(session, modifier, group)
