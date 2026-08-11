from __future__ import annotations

import secrets
from hashlib import sha256


def generate_api_key() -> tuple[str, str]:
    raw = f"pmla_{secrets.token_urlsafe(48)}"
    prefix = raw[:10]
    hashed = sha256(raw.encode()).hexdigest()
    return raw, f"{prefix}...{hashed[:8]}"


def hash_api_key(key: str) -> str:
    return sha256(key.encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    return secrets.compare_digest(hash_api_key(plain_key), hashed_key)
