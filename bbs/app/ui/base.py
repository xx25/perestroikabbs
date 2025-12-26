"""
Base class for UI modules.

Provides common functionality and consistent patterns across all UI modules.
"""

from abc import ABC, abstractmethod
from typing import Callable, Generic, Optional, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from ..session import Session
    from ..storage.container import RepositoryContainer

T = TypeVar('T')


class UIModule(ABC, Generic[T]):
    """
    Abstract base class for all UI modules.

    Provides:
    - Standard constructor with session and optional repos
    - Access level checking
    - Common UI utilities (error display, confirmation, etc.)
    - Abstract run() method for main logic
    """

    def __init__(
        self,
        session: "Session",
        repos: Optional["RepositoryContainer"] = None,
    ):
        """
        Initialize the UI module.

        Args:
            session: The current session
            repos: Optional repository container (defaults to global singleton)
        """
        self.session = session
        if repos is None:
            from ..storage.container import get_repos
            repos = get_repos()
        self.repos = repos

    @property
    def min_access_level(self) -> int:
        """
        Minimum access level required to use this module.

        Override in subclasses to require specific access levels.
        """
        return 0

    async def check_access(self) -> bool:
        """
        Check if the current user has required access level.

        Returns:
            True if access is allowed, False otherwise.
        """
        if self.session.access_level < self.min_access_level:
            await self.session.writeline(
                f"\r\nAccess denied. Required level: {self.min_access_level}"
            )
            await self.session.writeline("Press any key to continue...")
            await self.session.read(1)
            return False
        return True

    @abstractmethod
    async def run(self) -> T:
        """
        Main entry point for the UI module.

        Override in subclasses to implement module logic.
        """
        pass

    async def show_error(self, message: str) -> None:
        """
        Display an error message and wait for acknowledgment.

        Args:
            message: Error message to display
        """
        await self.session.writeline(f"\r\nError: {message}")
        await self.session.writeline("Press any key to continue...")
        await self.session.read(1)

    async def show_message(self, message: str) -> None:
        """
        Display a message and wait for acknowledgment.

        Args:
            message: Message to display
        """
        await self.session.writeline(f"\r\n{message}")
        await self.session.writeline("Press any key to continue...")
        await self.session.read(1)

    async def confirm(self, message: str) -> bool:
        """
        Ask for confirmation.

        Args:
            message: Confirmation prompt

        Returns:
            True if user confirms, False otherwise.
        """
        response = await self.session.readline(f"{message} (Y/N): ")
        return response.upper() == 'Y'

    async def input_with_validation(
        self,
        prompt: str,
        validator: Callable[[str], bool],
        error_message: str = "Invalid input",
        allow_empty: bool = False,
    ) -> Optional[str]:
        """
        Get input with validation loop.

        Args:
            prompt: Input prompt
            validator: Validation function returning True if valid
            error_message: Message to show on validation failure
            allow_empty: If True, empty input returns None immediately

        Returns:
            Validated input string, or None if empty and allow_empty=True
        """
        while True:
            value = await self.session.readline(prompt)
            if not value:
                if allow_empty:
                    return None
                await self.session.writeline(error_message)
                continue
            if validator(value):
                return value
            await self.session.writeline(error_message)

    async def clear_and_header(self, title: str) -> None:
        """
        Clear screen and display a header.

        Args:
            title: Title to display in header
        """
        await self.session.clear_screen()
        await self.session.writeline(f"=== {title} ===")
        await self.session.writeline()

    async def show_table_header(self, columns: str) -> None:
        """
        Display a table header with separator.

        Args:
            columns: Column headers line
        """
        await self.session.writeline(columns)
        await self.session.writeline("-" * len(columns))

    async def pause(self, message: str = "Press any key to continue...") -> None:
        """
        Wait for keypress.

        Args:
            message: Message to display
        """
        await self.session.writeline(f"\r\n{message}")
        await self.session.read(1)
