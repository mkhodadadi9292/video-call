"""PBKDF2-HMAC-SHA256 password hashing (implements the PasswordHasher port)."""

import hashlib
import secrets

from backend.domain.ports.password_hasher import PasswordHasher

_ITERATIONS = 100_000


class Pbkdf2PasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
        return f"{salt}${digest}"

    def verify(self, password: str, hashed: str) -> bool:
        try:
            salt, expected = hashed.split("$", 1)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
        return secrets.compare_digest(digest, expected)


hash_password = Pbkdf2PasswordHasher().hash
verify_password = Pbkdf2PasswordHasher().verify
