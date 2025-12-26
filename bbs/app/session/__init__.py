"""
Session package - Facade for backward compatibility.

This module provides the Session class which delegates to specialized components:
- SessionState: Pure state/data
- SessionIO: Network I/O operations
- SessionDisplay: Terminal display and rendering

The facade maintains full backward compatibility with the original Session API.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from telnetlib3 import TelnetReader, TelnetWriter

from ..encoding import CodecIO
from ..i18n import Translator
from ..display import DisplayMode
from ..templates import TemplateEngine
from ..utils.logger import get_logger

from .state import (
    SessionState,
    SessionData,
    SessionTransport,
    ClientCapabilities,
)
from .io import SessionIO
from .display import SessionDisplay

# Re-export for backward compatibility
__all__ = [
    'Session',
    'SessionState',
    'SessionData',
    'SessionTransport',
    'ClientCapabilities',
    'SessionIO',
    'SessionDisplay',
]

logger = get_logger("session")


@dataclass
class Session:
    """
    Session facade maintaining backward compatibility.

    Delegates to SessionState, SessionIO, and SessionDisplay components
    while exposing the same API as the original monolithic Session class.
    """

    # Public fields for direct access (backward compatibility)
    id: str = field(default="")
    reader: Optional[TelnetReader] = None
    writer: Optional[TelnetWriter] = None
    state: SessionState = SessionState.CONNECTING
    transport_type: SessionTransport = SessionTransport.TELNET
    user_id: Optional[int] = None
    username: Optional[str] = None
    access_level: int = 0
    capabilities: ClientCapabilities = field(default_factory=ClientCapabilities)
    codec: CodecIO = field(default_factory=lambda: CodecIO("utf-8"))
    translator: Translator = field(default_factory=lambda: Translator("en"))
    language: str = "en"
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    remote_addr: Optional[str] = None
    remote_port: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    _input_buffer: str = ""
    _output_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    display_mode: DisplayMode = DisplayMode.STANDARD_ANSI
    template_engine: Optional[TemplateEngine] = None

    # Internal components (created in __post_init__)
    _state_component: Optional[SessionData] = field(default=None, init=False, repr=False)
    _io_component: Optional[SessionIO] = field(default=None, init=False, repr=False)
    _display_component: Optional[SessionDisplay] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize components and wire them together."""
        # Create state component
        self._state_component = SessionData(
            id=self.id if self.id else None,  # Will auto-generate if empty
            state=self.state,
            transport_type=self.transport_type,
            user_id=self.user_id,
            username=self.username,
            access_level=self.access_level,
            language=self.language,
            connected_at=self.connected_at,
            last_activity=self.last_activity,
            remote_addr=self.remote_addr,
            remote_port=self.remote_port,
            data=self.data,
            capabilities=self.capabilities,
        )

        # Sync id back (may have been auto-generated)
        self.id = self._state_component.id

        # Create I/O component
        self._io_component = SessionIO(
            reader=self.reader,
            writer=self.writer,
            codec=self.codec,
            _input_buffer=self._input_buffer,
            _output_queue=self._output_queue,
            _state=self._state_component,
        )

        # Create display component
        self._display_component = SessionDisplay(
            display_mode=self.display_mode,
            template_engine=self.template_engine,
            _io=self._io_component,
            _state=self._state_component,
        )

        # Extract peer info from transport
        if self.writer:
            peer = self.writer.transport.get_extra_info("peername")
            if peer:
                self.remote_addr = peer[0]
                self.remote_port = peer[1]
                self._state_component.remote_addr = peer[0]
                self._state_component.remote_port = peer[1]

    def _sync_to_components(self) -> None:
        """Sync facade fields to components (for direct field modifications)."""
        if self._state_component:
            self._state_component.state = self.state
            self._state_component.user_id = self.user_id
            self._state_component.username = self.username
            self._state_component.access_level = self.access_level
            self._state_component.language = self.language
            self._state_component.data = self.data

    def _sync_from_components(self) -> None:
        """Sync component fields back to facade."""
        if self._state_component:
            self.state = self._state_component.state
            self.user_id = self._state_component.user_id
            self.username = self._state_component.username
            self.access_level = self._state_component.access_level
            self.language = self._state_component.language
            self.last_activity = self._state_component.last_activity

        if self._display_component:
            self.display_mode = self._display_component.display_mode

    # === I/O Methods (delegated to SessionIO) ===

    async def negotiate(self) -> None:
        """Perform telnet protocol negotiation."""
        self._sync_to_components()
        await self._io_component.negotiate()
        self._sync_from_components()

    async def detect_ripscrip(self) -> None:
        """Detect RIPscrip capability."""
        await self._io_component.detect_ripscrip()

    async def write(self, data: bytes | str) -> None:
        """Write text data with proper encoding."""
        await self._io_component.write(data)
        self._sync_from_components()

    async def writeline(self, text: str = "") -> None:
        """Write text followed by CRLF."""
        await self._io_component.writeline(text)
        self._sync_from_components()

    async def read(self, size: int = 1) -> str:
        """Read text with proper decoding."""
        result = await self._io_component.read(size)
        self._sync_from_components()
        return result

    async def write_raw(self, data: bytes) -> None:
        """Write raw bytes directly to the transport."""
        await self._io_component.write_raw(data)
        self._sync_from_components()

    async def read_raw(self, size: int, timeout: float = 10.0) -> Optional[bytes]:
        """Read raw bytes for binary file transfers."""
        result = await self._io_component.read_raw(size, timeout)
        self._sync_from_components()
        return result

    async def readline(self, prompt: str = "", echo: bool = True, max_length: int = 255) -> str:
        """Read a line of input with proper encoding support."""
        result = await self._io_component.readline(prompt, echo, max_length)
        self._sync_from_components()
        return result

    async def read_password(self, prompt: str = "Password: ", max_length: int = 64) -> str:
        """Read password input without echo."""
        return await self._io_component.read_password(prompt, max_length)

    async def disconnect(self) -> None:
        """Disconnect the session."""
        await self._io_component.disconnect()
        self._sync_from_components()
        self.reader = None
        self.writer = None

    def set_encoding(self, encoding: str) -> None:
        """Set the session's character encoding."""
        self._io_component.set_encoding(encoding)
        self.codec = self._io_component.codec
        self.capabilities.encoding = encoding
        logger.info(f"Session {self.id}: Encoding set to {encoding}")

    # === Display Methods (delegated to SessionDisplay) ===

    async def clear_screen(self) -> None:
        """Clear the terminal screen."""
        await self._display_component.clear_screen()

    async def set_cursor(self, row: int, col: int) -> None:
        """Set cursor position."""
        await self._display_component.set_cursor(row, col)

    async def set_color(
        self, fg: Optional[int] = None, bg: Optional[int] = None, bold: bool = False
    ) -> None:
        """Set terminal colors."""
        await self._display_component.set_color(fg, bg, bold)

    async def reset_color(self) -> None:
        """Reset terminal colors to default."""
        await self._display_component.reset_color()

    async def pause(self, message: str = "--More--") -> None:
        """Display a pause message and wait for keypress."""
        await self._display_component.pause(message)

    async def menu_select(
        self, options: list[tuple[str, str]], prompt: str = "Select: "
    ) -> Optional[str]:
        """Display a simple menu and get user selection."""
        return await self._display_component.menu_select(options, prompt)

    def update_display_mode(self) -> None:
        """Update display mode based on current capabilities."""
        self._display_component.update_display_mode()
        self.display_mode = self._display_component.display_mode
        logger.info(f"Session {self.id}: Display mode set to {self.display_mode.value}")

    async def render_template(self, template_name: str, **context) -> None:
        """Render and display a template."""
        self._sync_to_components()
        await self._display_component.render_template(template_name, **context)

    # === State Methods (delegated to SessionState) ===

    def is_authenticated(self) -> bool:
        """Check if the session is authenticated."""
        self._sync_to_components()
        return self._state_component.is_authenticated()

    def get_session_time(self) -> str:
        """Get formatted session duration."""
        return self._state_component.get_session_time()

    # === Translation Methods (kept on facade) ===

    def t(self, key: str, **kwargs) -> str:
        """Translate a string using the session's current language."""
        return self.translator.get(key, **kwargs)

    def set_language(self, lang_code: str) -> bool:
        """Change the session's language."""
        if self.translator.set_language(lang_code):
            self.language = lang_code
            if self._state_component:
                self._state_component.language = lang_code
            # Suggest appropriate encoding for Russian
            if lang_code == 'ru' and self.capabilities.encoding not in ['utf-8', 'windows-1251', 'koi8-r']:
                logger.info(f"Session {self.id}: Suggesting Russian-compatible encoding")
            return True
        return False
