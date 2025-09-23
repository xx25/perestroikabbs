import hashlib
import secrets
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger("security.auth")


class AuthManager:
    def __init__(self):
        config = get_config().security
        self.hasher = PasswordHasher(
            time_cost=config.argon2_time_cost,
            memory_cost=config.argon2_memory_cost,
            parallelism=config.argon2_parallelism,
        )
        self.min_password_length = config.min_password_length
        self.require_secure = config.require_secure_passwords

    async def hash_password(self, password: str) -> str:
        try:
            return self.hasher.hash(password)
        except Exception as e:
            logger.error(f"Error hashing password: {e}")
            raise

    async def verify_password(self, password: str, hash: str) -> bool:
        try:
            self.hasher.verify(hash, password)

            if self.hasher.check_needs_rehash(hash):
                return True

            return True
        except (VerifyMismatchError, VerificationError):
            return False
        except InvalidHash:
            logger.warning("Invalid password hash format")
            return False
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False

    def is_password_secure(self, password: str, username: Optional[str] = None) -> tuple[bool, str]:
        if len(password) < self.min_password_length:
            return False, f"Password must be at least {self.min_password_length} characters"

        if not self.require_secure:
            return True, "OK"

        if username and username.lower() in password.lower():
            return False, "Password cannot contain username"

        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        complexity = sum([has_lower, has_upper, has_digit, has_special])

        if complexity < 3:
            return False, "Password must contain at least 3 of: lowercase, uppercase, digit, special character"

        common_passwords = [
            "password", "12345678", "qwerty", "abc123", "password123",
            "admin", "letmein", "welcome", "monkey", "dragon"
        ]

        if password.lower() in common_passwords:
            return False, "Password is too common"

        return True, "OK"

    @staticmethod
    def generate_session_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_api_key() -> str:
        return secrets.token_hex(32)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


class RateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = {}

    async def check_rate_limit(self, identifier: str) -> bool:
        import time
        current_time = time.time()

        if identifier not in self.attempts:
            self.attempts[identifier] = []

        self.attempts[identifier] = [
            t for t in self.attempts[identifier]
            if current_time - t < self.window_seconds
        ]

        if len(self.attempts[identifier]) >= self.max_attempts:
            return False

        self.attempts[identifier].append(current_time)
        return True

    async def reset(self, identifier: str) -> None:
        if identifier in self.attempts:
            del self.attempts[identifier]