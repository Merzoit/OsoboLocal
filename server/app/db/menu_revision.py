from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import SyncState

MENU_REVISION_KEY = "menu_revision"


def get_menu_revision(session: Session) -> int:
    state = session.get(SyncState, MENU_REVISION_KEY)
    if state is None:
        return 0
    return int(state.value)


def bump_menu_revision(session: Session) -> int:
    """Increment the global menu revision counter in the current transaction."""
    now = datetime.now(UTC)
    state = session.get(SyncState, MENU_REVISION_KEY)
    if state is None:
        state = SyncState(key=MENU_REVISION_KEY, value="0", updated_at=now)
        session.add(state)
        session.flush()
    new_value = int(state.value) + 1
    state.value = str(new_value)
    state.updated_at = now
    session.flush()
    return new_value
