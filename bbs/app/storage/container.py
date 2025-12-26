"""
Repository container for dependency injection.

Provides a single point of access to all repositories, enabling:
- Lazy initialization of repositories
- Easy mocking for tests
- Consistent access patterns across UI modules
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .repositories import (
        UserRepository,
        BoardRepository,
        ChatRepository,
        FileRepository,
        MailRepository,
        SystemRepository,
    )


@dataclass
class RepositoryContainer:
    """
    Dependency injection container for repositories.

    Repositories are lazily initialized on first access.
    """

    _user_repo: Optional["UserRepository"] = field(default=None, init=False)
    _board_repo: Optional["BoardRepository"] = field(default=None, init=False)
    _chat_repo: Optional["ChatRepository"] = field(default=None, init=False)
    _file_repo: Optional["FileRepository"] = field(default=None, init=False)
    _mail_repo: Optional["MailRepository"] = field(default=None, init=False)
    _system_repo: Optional["SystemRepository"] = field(default=None, init=False)

    @property
    def users(self) -> "UserRepository":
        """Get user repository (lazy initialized)."""
        if self._user_repo is None:
            from .repositories import UserRepository
            self._user_repo = UserRepository()
        return self._user_repo

    @property
    def boards(self) -> "BoardRepository":
        """Get board repository (lazy initialized)."""
        if self._board_repo is None:
            from .repositories import BoardRepository
            self._board_repo = BoardRepository()
        return self._board_repo

    @property
    def chat(self) -> "ChatRepository":
        """Get chat repository (lazy initialized)."""
        if self._chat_repo is None:
            from .repositories import ChatRepository
            self._chat_repo = ChatRepository()
        return self._chat_repo

    @property
    def files(self) -> "FileRepository":
        """Get file repository (lazy initialized)."""
        if self._file_repo is None:
            from .repositories import FileRepository
            self._file_repo = FileRepository()
        return self._file_repo

    @property
    def mail(self) -> "MailRepository":
        """Get mail repository (lazy initialized)."""
        if self._mail_repo is None:
            from .repositories import MailRepository
            self._mail_repo = MailRepository()
        return self._mail_repo

    @property
    def system(self) -> "SystemRepository":
        """Get system repository (lazy initialized)."""
        if self._system_repo is None:
            from .repositories import SystemRepository
            self._system_repo = SystemRepository()
        return self._system_repo


# Global singleton instance
_container: Optional[RepositoryContainer] = None


def get_repos() -> RepositoryContainer:
    """
    Get the global repository container singleton.

    Returns:
        The shared RepositoryContainer instance.
    """
    global _container
    if _container is None:
        _container = RepositoryContainer()
    return _container


def reset_repos() -> None:
    """
    Reset the global repository container (for testing).
    """
    global _container
    _container = None
