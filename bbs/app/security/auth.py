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
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, ban_duration: int = 3600):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.ban_duration = ban_duration  # Ban duration in seconds
        self.attempts: dict[str, list[float]] = {}
        self.banned_ips: dict[str, float] = {}  # IP -> ban expiry time
        self.permanent_bans: set[str] = set()  # Permanently banned IPs

    async def check_rate_limit(self, identifier: str) -> bool:
        import time
        current_time = time.time()

        # Check if IP is permanently banned
        if identifier in self.permanent_bans:
            logger.warning(f"Permanently banned IP attempted access: {identifier}")
            return False

        # Check if IP is temporarily banned
        if identifier in self.banned_ips:
            if current_time < self.banned_ips[identifier]:
                logger.warning(f"Temporarily banned IP attempted access: {identifier}")
                return False
            else:
                # Ban has expired, remove it
                del self.banned_ips[identifier]

        if identifier not in self.attempts:
            self.attempts[identifier] = []

        self.attempts[identifier] = [
            t for t in self.attempts[identifier]
            if current_time - t < self.window_seconds
        ]

        if len(self.attempts[identifier]) >= self.max_attempts:
            # Auto-ban after max attempts
            await self.ban_ip(identifier, self.ban_duration)
            logger.warning(f"IP {identifier} auto-banned after {self.max_attempts} attempts")
            return False

        self.attempts[identifier].append(current_time)
        return True

    async def reset(self, identifier: str) -> None:
        if identifier in self.attempts:
            del self.attempts[identifier]

    async def ban_ip(self, ip: str, duration: Optional[int] = None) -> None:
        """Ban an IP address for a specified duration or permanently"""
        import time
        if duration is None:
            # Permanent ban
            self.permanent_bans.add(ip)
            logger.info(f"IP {ip} permanently banned")
        else:
            # Temporary ban
            self.banned_ips[ip] = time.time() + duration
            logger.info(f"IP {ip} banned for {duration} seconds")

    async def unban_ip(self, ip: str) -> bool:
        """Remove an IP from the ban list"""
        removed = False
        if ip in self.permanent_bans:
            self.permanent_bans.remove(ip)
            removed = True
        if ip in self.banned_ips:
            del self.banned_ips[ip]
            removed = True
        if removed:
            logger.info(f"IP {ip} unbanned")
        return removed

    async def is_banned(self, ip: str) -> bool:
        """Check if an IP is currently banned"""
        import time
        if ip in self.permanent_bans:
            return True
        if ip in self.banned_ips:
            if time.time() < self.banned_ips[ip]:
                return True
            else:
                # Ban expired, clean up
                del self.banned_ips[ip]
        return False

    async def get_banned_ips(self) -> dict:
        """Get list of all banned IPs with their status"""
        import time
        current_time = time.time()
        result = {}

        for ip in self.permanent_bans:
            result[ip] = {'type': 'permanent', 'expires': None}

        for ip, expiry in list(self.banned_ips.items()):
            if current_time < expiry:
                result[ip] = {
                    'type': 'temporary',
                    'expires': expiry,
                    'remaining': int(expiry - current_time)
                }
            else:
                # Expired, remove
                del self.banned_ips[ip]

        return result

    async def save_bans(self, filepath: str) -> None:
        """Save ban list to file for persistence"""
        import json
        data = {
            'permanent_bans': list(self.permanent_bans),
            'temporary_bans': self.banned_ips
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save ban list: {e}")

    async def load_bans(self, filepath: str) -> None:
        """Load ban list from file"""
        import json
        import os
        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.permanent_bans = set(data.get('permanent_bans', []))
                self.banned_ips = data.get('temporary_bans', {})
                logger.info(f"Loaded {len(self.permanent_bans)} permanent bans, {len(self.banned_ips)} temporary bans")
        except Exception as e:
            logger.error(f"Failed to load ban list: {e}")