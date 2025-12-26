"""
Session display operations.

Handles terminal display, ANSI rendering, and template output.
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from ..display import DisplayMode
from ..templates import TemplateEngine
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .io import SessionIO
    from .state import SessionData, ClientCapabilities

logger = get_logger("session.display")


@dataclass
class SessionDisplay:
    """
    Handles terminal display and rendering operations.

    Depends on SessionIO for actual output and SessionState for capabilities.
    """

    display_mode: DisplayMode = DisplayMode.STANDARD_ANSI
    template_engine: Optional[TemplateEngine] = None

    # References to other components
    _io: Optional["SessionIO"] = None
    _state: Optional["SessionData"] = None

    @property
    def capabilities(self) -> "ClientCapabilities":
        """Get capabilities from state."""
        if self._state:
            return self._state.capabilities
        from .state import ClientCapabilities
        return ClientCapabilities()

    async def clear_screen(self) -> None:
        """Clear the terminal screen."""
        if not self._io:
            return

        if self.capabilities.ansi:
            await self._io.write(b"\x1b[2J\x1b[H")
        else:
            await self._io.write(b"\r\n" * self.capabilities.rows)

    async def set_cursor(self, row: int, col: int) -> None:
        """Set cursor position (1-indexed)."""
        if not self._io:
            return

        if self.capabilities.ansi:
            await self._io.write(f"\x1b[{row};{col}H")

    async def set_color(
        self, fg: Optional[int] = None, bg: Optional[int] = None, bold: bool = False
    ) -> None:
        """
        Set terminal colors.

        Args:
            fg: Foreground color (0-7 for standard ANSI colors)
            bg: Background color (0-7 for standard ANSI colors)
            bold: Enable bold/bright attribute
        """
        if not self._io:
            return

        if not self.capabilities.ansi or not self.capabilities.color:
            return

        codes = []
        if bold:
            codes.append("1")
        if fg is not None:
            codes.append(str(30 + fg))
        if bg is not None:
            codes.append(str(40 + bg))

        if codes:
            await self._io.write(f"\x1b[{';'.join(codes)}m")

    async def reset_color(self) -> None:
        """Reset terminal colors to default."""
        if not self._io:
            return

        if self.capabilities.ansi:
            await self._io.write(b"\x1b[0m")

    async def pause(self, message: str = "--More--") -> None:
        """Display a pause message and wait for keypress."""
        if not self._io:
            return

        await self._io.write(f"\r\n{message}")
        await self._io.read(1)
        await self._io.write(f"\r{' ' * len(message)}\r")

    async def menu_select(
        self, options: list[tuple[str, str]], prompt: str = "Select: "
    ) -> Optional[str]:
        """
        Display a simple menu and get user selection.

        Args:
            options: List of (key, description) tuples
            prompt: Input prompt

        Returns:
            Selected key or None
        """
        if not self._io:
            return None

        for key, desc in options:
            await self._io.writeline(f"  [{key}] {desc}")

        while True:
            choice = (await self._io.readline(prompt)).upper()
            for key, _ in options:
                if choice == key.upper():
                    return key

            await self._io.writeline("Invalid selection. Please try again.")

    def update_display_mode(self) -> None:
        """Update display mode based on current capabilities."""
        if self.capabilities.cols == 40:
            self.display_mode = (
                DisplayMode.NARROW_ANSI if self.capabilities.ansi else DisplayMode.NARROW_PLAIN
            )
        else:
            self.display_mode = (
                DisplayMode.STANDARD_ANSI if self.capabilities.ansi else DisplayMode.STANDARD_PLAIN
            )
        if self._state:
            logger.info(f"Session {self._state.id}: Display mode set to {self.display_mode.value}")

    async def render_template(self, template_name: str, **context) -> None:
        """
        Render and display a template.

        Args:
            template_name: Name of template (e.g., 'motd', 'menus/main')
            **context: Template context variables
        """
        if not self._io or not self._state:
            return

        if not self.template_engine:
            self.template_engine = TemplateEngine()

        # Add session context
        context.setdefault('username', self._state.username or 'Guest')
        context.setdefault('access_level', self._state.access_level)
        context.setdefault('last_login', self._state.last_activity.strftime("%Y-%m-%d %H:%M"))
        context.setdefault('session_time', self._state.get_session_time())

        # Render template
        content = await self.template_engine.render(
            template_name=template_name,
            context=context,
            display_mode=self.display_mode,
            encoding=self._state.capabilities.encoding,
            language=self._state.language
        )

        # Write to session
        await self._io.write(content)
