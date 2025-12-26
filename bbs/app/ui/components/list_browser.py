"""
Paginated list browser component.

Provides a reusable component for displaying and navigating paginated lists,
with support for item selection and custom commands.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, List, Optional, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from ...session import Session

T = TypeVar('T')


@dataclass
class ListColumn(Generic[T]):
    """
    Column definition for list display.

    Attributes:
        header: Column header text
        width: Column width in characters
        accessor: Function to extract column value from item
        align: Text alignment ('left', 'right', 'center')
    """

    header: str
    width: int
    accessor: Callable[[T], str]
    align: str = 'left'  # 'left', 'right', 'center'


class ListBrowser(Generic[T]):
    """
    Reusable paginated list browser with selection.

    Used by boards, mail, files, users, and admin modules for
    consistent list display and navigation.
    """

    def __init__(
        self,
        session: "Session",
        title: str,
        columns: List[ListColumn[T]],
        items: List[T],
        page_size: int = 20,
    ):
        """
        Initialize the list browser.

        Args:
            session: Current session
            title: List title
            columns: Column definitions
            items: List items to display
            page_size: Items per page
        """
        self.session = session
        self.title = title
        self.columns = columns
        self.items = items
        self.page_size = page_size
        self.current_page = 0

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return max(1, (len(self.items) + self.page_size - 1) // self.page_size)

    @property
    def current_items(self) -> List[T]:
        """Get items for current page."""
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def _format_value(self, value: str, width: int, align: str) -> str:
        """Format a value with specified width and alignment."""
        if len(value) > width:
            value = value[:width - 1] + "…"
        if align == 'right':
            return value.rjust(width)
        elif align == 'center':
            return value.center(width)
        return value.ljust(width)

    async def render_header(self) -> None:
        """Render column headers with separator."""
        header_line = ""
        separator_line = ""

        for col in self.columns:
            header_line += self._format_value(col.header, col.width, col.align) + " "
            separator_line += "-" * col.width + " "

        await self.session.writeline(header_line.rstrip())
        await self.session.writeline(separator_line.rstrip())

    async def render_item(self, index: int, item: T) -> None:
        """Render a single item row."""
        line = f"[{index + 1:>3}] "
        for col in self.columns:
            value = col.accessor(item)
            line += self._format_value(value, col.width, col.align) + " "
        await self.session.writeline(line.rstrip())

    async def render(self) -> None:
        """Render the full list view."""
        await self.session.clear_screen()
        await self.session.writeline(f"=== {self.title} ===")
        await self.session.writeline()

        if not self.items:
            await self.session.writeline("No items to display.")
            return

        await self.render_header()

        start_idx = self.current_page * self.page_size
        for i, item in enumerate(self.current_items):
            await self.render_item(start_idx + i, item)

        await self.session.writeline()
        await self.session.writeline(f"Page {self.current_page + 1} of {self.total_pages}")

    async def browse(
        self,
        commands: Optional[dict[str, tuple[str, Callable[[T], Awaitable[None]]]]] = None,
        on_select: Optional[Callable[[T], Awaitable[None]]] = None,
    ) -> Optional[T]:
        """
        Display list and handle navigation/selection.

        Args:
            commands: Dict mapping command keys to (label, handler) tuples
                      e.g., {'D': ('Download', download_handler), 'V': ('View', view_handler)}
            on_select: Optional callback when item is selected by number

        Returns:
            Selected item if on_select is None and user selects, otherwise None
        """
        while True:
            await self.render()

            # Build navigation help
            nav_parts = []
            if self.total_pages > 1:
                nav_parts.append("[N]ext [P]rev")

            # Add command help
            if commands:
                for key, (label, _) in commands.items():
                    nav_parts.append(f"[{key}]{label}")

            nav_parts.append("[Q]uit")
            await self.session.writeline(" ".join(nav_parts))

            choice = await self.session.readline("Selection: ")
            upper_choice = choice.upper().strip()

            if upper_choice == 'Q':
                return None
            elif upper_choice == 'N' and self.current_page < self.total_pages - 1:
                self.current_page += 1
            elif upper_choice == 'P' and self.current_page > 0:
                self.current_page -= 1
            elif upper_choice in (commands or {}):
                # Command selected - get item number
                item_input = await self.session.readline("Item number: ")
                try:
                    idx = int(item_input) - 1
                    if 0 <= idx < len(self.items):
                        _, handler = commands[upper_choice]
                        await handler(self.items[idx])
                    else:
                        await self.session.writeline("Invalid item number.")
                except ValueError:
                    await self.session.writeline("Please enter a number.")
            elif choice.isdigit():
                # Direct item selection
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.items):
                        if on_select:
                            await on_select(self.items[idx])
                        else:
                            return self.items[idx]
                    else:
                        await self.session.writeline("Invalid selection.")
                except ValueError:
                    pass
            elif choice:
                await self.session.writeline("Invalid selection.")
