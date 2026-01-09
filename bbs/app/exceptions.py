"""
Custom exception hierarchy for Perestroika BBS.

This module provides a structured exception hierarchy for consistent
error handling across the application.
"""


class BBSException(Exception):
    """Base exception for all BBS errors."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class AuthenticationError(BBSException):
    """Authentication-related errors (login failures, invalid credentials)."""

    pass


class AuthorizationError(BBSException):
    """Access level/permission errors (insufficient privileges)."""

    pass


class SessionError(BBSException):
    """Session lifecycle errors (connection issues, state transitions)."""

    pass


class ConnectionError(BBSException):
    """Transport/connection errors (network issues, disconnects)."""

    pass


class ConnectionClosedError(ConnectionError):
    """Connection has been closed (client disconnected)."""

    pass


class StorageError(BBSException):
    """Database/repository errors (query failures, constraint violations)."""

    pass


class TransferError(BBSException):
    """File transfer protocol errors (XMODEM, ZMODEM, Kermit failures)."""

    pass


class ConfigurationError(BBSException):
    """Configuration validation errors (invalid settings, missing values)."""

    pass


class ValidationError(BBSException):
    """Input validation errors (invalid user input, format errors)."""

    pass


class RateLimitError(AuthenticationError):
    """Rate limiting triggered (too many attempts)."""

    pass


class BannedError(AuthenticationError):
    """IP or user is banned."""

    pass
