from __future__ import annotations

import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{actual_salt}:{password}".encode("utf-8")).hexdigest()
    return f"{actual_salt}:{digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected = password_hash.split(":", 1)
    except ValueError:
        return False
    actual = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return secrets.compare_digest(actual, expected)


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)
