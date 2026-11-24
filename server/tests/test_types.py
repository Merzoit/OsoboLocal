from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.db.types import UTCDateTime
from app.ids import new_uuid


def test_utc_datetime_rejects_naive() -> None:
    col = UTCDateTime()
    with pytest.raises(ValueError, match="Naive"):
        col.process_bind_param(datetime(2026, 1, 1, 12, 0, 0), dialect=None)


def test_utc_datetime_normalizes() -> None:
    col = UTCDateTime()
    aware = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC)
    bound = col.process_bind_param(aware, dialect=None)
    assert bound == aware
    result = col.process_result_value(datetime(2026, 1, 1, 15, 0, 0), dialect=None)
    assert result is not None
    assert result.tzinfo is not None
    assert result.utcoffset() == UTC.utcoffset(None)


def test_new_uuid_is_stdlib_uuid() -> None:
    import uuid

    value = new_uuid()
    assert isinstance(value, uuid.UUID)
    assert value.version == 7
