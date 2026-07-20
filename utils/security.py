"""Dependency-free PBKDF2 password hashing."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets


ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 260_000
MAX_ACCEPTED_ITERATIONS = 2_000_000
SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("密码不能为空")
    if iterations < 100_000:
        raise ValueError("PBKDF2 迭代次数过低")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{ALGORITHM}${iterations}${salt_text}${digest_text}"


def _decode_urlsafe(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_password(password: str, encoded_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(encoded_hash, str):
        return False
    try:
        algorithm, iterations_text, salt_text, expected_text = encoded_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_text)
        if iterations < 1 or iterations > MAX_ACCEPTED_ITERATIONS:
            return False
        salt = _decode_urlsafe(salt_text)
        expected = _decode_urlsafe(expected_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


def password_needs_rehash(encoded_hash: str, *, iterations: int = DEFAULT_ITERATIONS) -> bool:
    try:
        algorithm, stored_iterations, _salt, _digest = encoded_hash.split("$", 3)
        return algorithm != ALGORITHM or int(stored_iterations) < iterations
    except (AttributeError, TypeError, ValueError):
        return True
