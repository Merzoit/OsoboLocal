from __future__ import annotations

import hashlib
import hmac
import secrets


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_registration_code() -> str:
    """Return a one-time registration code with at least 128 bits of entropy."""
    return secrets.token_urlsafe(16)  # 16 bytes = 128 bits


def generate_device_token() -> str:
    """Long random device token (256 bits)."""
    return secrets.token_urlsafe(32)


def constant_time_hash_equal(stored_hash: str, plaintext: str) -> bool:
    return hmac.compare_digest(stored_hash, sha256_hex(plaintext))
