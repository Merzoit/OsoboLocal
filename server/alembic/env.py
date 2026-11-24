from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from app.config import get_settings
from app.db import models as _models  # noqa: F401 — register models
from app.db.base import Base
from app.db.session import create_engine_from_url
from app.db.types import UTCDateTime

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url and not url.startswith("driver://"):
        settings_url = get_settings().database_url
        if url == "sqlite:///./data/ososbo.db":
            return settings_url
        return url
    return get_settings().database_url


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path in {":memory:", ""} or raw_path.startswith("file:"):
        return
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


def render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    if type_ == "type" and isinstance(obj, UTCDateTime):
        autogen_context.imports.add("from app.db.types import UTCDateTime")  # type: ignore[attr-defined]
        return "UTCDateTime()"
    return False


def run_migrations_offline() -> None:
    url = get_url()
    _ensure_sqlite_parent(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_url()
    _ensure_sqlite_parent(url)
    connectable = create_engine_from_url(url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
