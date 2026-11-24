from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.api.deps import DbSession
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, db: DbSession) -> dict[str, Any]:
    settings = get_settings()
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001 — health must not raise
        db_ok = False

    terminal = getattr(request.app.state, "terminal_status", "unknown")
    sync = getattr(request.app.state, "sync_status", "not_configured")

    return {
        "status": "ok" if db_ok else "degraded",
        "app_version": settings.app_version,
        "database": "ok" if db_ok else "error",
        "terminal": terminal,
        "sync": sync,
    }
