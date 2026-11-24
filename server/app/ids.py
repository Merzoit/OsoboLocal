"""UUID helpers. Always return stdlib uuid.UUID."""

from __future__ import annotations

import uuid

import uuid_utils


def new_uuid() -> uuid.UUID:
    """Generate a UUIDv7 and return it as ``uuid.UUID``."""
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
