"""Bounded salted password hashing for explicitly local demo users, never production SSO."""

import hashlib
import hmac
import secrets

ITERATIONS = 600000


def encode(password: str) -> str:
    if not 16 <= len(password) <= 128:
        raise ValueError("Demo password must contain 16–128 characters")
    salt = secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2-sha256${ITERATIONS}${salt}${value.hex()}"


def verify(password: str, encoded: str) -> bool:
    if not 1 <= len(password) <= 128:
        return False
    try:
        scheme, rounds, salt, expected = encoded.split("$")
        if scheme != "pbkdf2-sha256" or int(rounds) != ITERATIONS or len(salt) != 32:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False
