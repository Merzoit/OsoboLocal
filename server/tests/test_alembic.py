from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_upgrade_head_on_empty_db(tmp_path: Path) -> None:
    db_file = tmp_path / "empty.db"
    url = f"sqlite:///{db_file}"
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert "menu_item" in tables
    assert "payment" in tables
    assert "device_registration_code" in tables
    assert "alembic_version" in tables
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "2a9f5c1da9de"
    engine.dispose()


def test_alembic_check_matches_models(tmp_path: Path) -> None:
    db_file = tmp_path / "check.db"
    url = f"sqlite:///{db_file}"
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    # Raises if models diverge from DB schema
    command.check(cfg)
