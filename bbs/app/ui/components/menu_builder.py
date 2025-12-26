"""
Menu builder component.

Provides a fluent API for building menus with consistent styling
and access control.
"""

from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Optional, TYPE_CHECKING

from ...utils.logger import get_logger

if TYPE_CHECKING:
    from ...session import Session

logger = get_logger("ui.menu_builder")


@dataclass
class MenuOption:
    """
    A single menu option.

    Attributes:
        key: Selection key (e.g., '1', 'A', 'Q')
        label: Display label
        handler: Async function to call when selected
        min_access: Minimum access level required
        enabled: Whether the option is enabled
    """

    key: str
    label: str
    handler: Optional[Callable[[], Awaitable[None]]] = None
    min_access: int = 0
    enabled: bool = True


class MenuBuilder:
    """
    Fluent API for building menus.

    Reduces boilerplate in menu creation and provides consistent
    rendering and access control.
    """

    def __init__(self, session: "Session", title: str):
        """
        Initialize the menu builder.

        Args:
            session: Current session
            title: Menu title
        """
        self.session = session
        self.title = title
        self.options: List[MenuOption] = []
        self._running = True

    def option(
        self,
        key: str,
        label: str,
        handler: Optional[Callable[[], Awaitable[None]]] = None,
        min_access: int = 0,
        enabled: bool = True,
    ) -> "MenuBuilder":
        """
        Add a menu option.

        Args:
            key: Selection key
            label: Display label
            handler: Handler function (None for quit/back)
            min_access: Minimum access level
            enabled: Whether enabled

        Returns:
            Self for chaining
        """
        self.options.append(MenuOption(
            key=key.upper(),
            label=label,
            handler=handler,
            min_access=min_access,
            enabled=enabled,
        ))
        return self

    def separator(self) -> "MenuBuilder":
        """
        Add a visual separator.

        Returns:
            Self for chaining
        """
        self.options.append(MenuOption(
            key="",
            label="---",
            enabled=False,
        ))
        return self

    def back(self, key: str = "Q", label: str = "Back") -> "MenuBuilder":
        """
        Add a back/quit option.

        Args:
            key: Selection key
            label: Display label

        Returns:
            Self for chaining
        """
        return self.option(key, label, handler=None)

    async def _render_ansi(self) -> None:
        """Render menu with ANSI box drawing and colors."""
        # Calculate width
        width = max(
            len(self.title),
            max(
                (len(f"[{o.key}] {o.label}") for o in self.options if o.enabled),
                default=10
            )
        ) + 4

        # Draw box
        await self.session.set_color(fg=3, bold=True)
        await self.session.writeline("╔" + "═" * width + "╗")
        await self.session.writeline("║ " + self.title.center(width - 2) + " ║")
        await self.session.writeline("╟" + "─" * width + "╢")
        await self.session.reset_color()

        # Draw options
        for opt in self.options:
            if not opt.enabled:
                continue
            if self.session.access_level >= opt.min_access:
                await self.session.set_color(fg=6)
                key_part = f"[{opt.key}]" if opt.key else "   "
                await self.session.write(f"║ {key_part} ")
                await self.session.set_color(fg=7)
                label_width = width - len(key_part) - 3
                await self.session.writeline(f"{opt.label.ljust(label_width)} ║")

        await self.session.set_color(fg=3, bold=True)
        await self.session.writeline("╚" + "═" * width + "╝")
        await self.session.reset_color()

    async def _render_plain(self) -> None:
        """Render menu with plain text."""
        width = 40
        await self.session.writeline("=" * width)
        await self.session.writeline(self.title.center(width))
        await self.session.writeline("-" * width)

        for opt in self.options:
            if opt.enabled and self.session.access_level >= opt.min_access:
                if opt.key:
                    await self.session.writeline(f"  [{opt.key}] {opt.label}")
                else:
                    await self.session.writeline(f"  {opt.label}")

        await self.session.writeline("=" * width)

    async def render(self) -> None:
        """Render the menu based on terminal capabilities."""
        await self.session.clear_screen()

        if self.session.capabilities.ansi:
            await self._render_ansi()
        else:
            await self._render_plain()

    async def run(self) -> Optional[str]:
        """
        Display menu and handle selection loop.

        Returns:
            The key of the last executed option, or None if quit
        """
        last_key = None
        self._running = True

        while self._running:
            await self.render()
            await self.session.writeline()

            choice = (await self.session.readline("Your choice: ")).upper().strip()

            for opt in self.options:
                if opt.key == choice and opt.enabled:
                    if self.session.access_level < opt.min_access:
                        await self.session.writeline("Access denied.")
                        await self.session.read(1)
                        break

                    if opt.handler is None:
                        # Quit/back option
                        self._running = False
                        return None

                    try:
                        await opt.handler()
                        last_key = choice
                    except Exception as e:
                        logger.error(f"Menu handler error: {e}")
                        await self.session.writeline(f"\r\nError: {e}")
                        await self.session.read(1)
                    break
            else:
                if choice:
                    await self.session.writeline("Invalid selection.")

        return last_key

    async def run_once(self) -> Optional[str]:
        """
        Display menu and handle single selection.

        Returns:
            The key of the selected option, or None if quit
        """
        await self.render()
        await self.session.writeline()

        choice = (await self.session.readline("Your choice: ")).upper().strip()

        for opt in self.options:
            if opt.key == choice and opt.enabled:
                if self.session.access_level < opt.min_access:
                    await self.session.writeline("Access denied.")
                    return None

                if opt.handler is None:
                    return None

                try:
                    await opt.handler()
                    return choice
                except Exception as e:
                    logger.error(f"Menu handler error: {e}")
                    await self.session.writeline(f"\r\nError: {e}")
                    return None

        if choice:
            await self.session.writeline("Invalid selection.")
        return None

    def stop(self) -> None:
        """Stop the menu loop."""
        self._running = False
