from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade_head(database_url: str) -> None:
    """Apply Alembic migrations to head.

    Deferred (not implemented in stage 1): VACUUM/backup of the DB file before migrate.
    """
    if database_url.startswith("sqlite:///"):
        raw = database_url.removeprefix("sqlite:///")
        if raw not in {":memory:", ""} and not raw.startswith("file:"):
            path = Path(raw)
            if not path.is_absolute():
                path = Path.cwd() / path
            path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Applying database migrations to head")
    command.upgrade(_alembic_config(database_url), "head")
