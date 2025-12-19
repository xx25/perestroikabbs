import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from telnetlib3 import TelnetReader, TelnetWriter, DO, WILL, WONT, DONT, BINARY, ECHO, NAWS, TTYPE

from .encoding import CodecIO
from .i18n import Translator
from .utils.logger import get_logger
from .templates import TemplateEngine, DisplayMode, DisplayConfig

logger = get_logger("session")


class SessionState(Enum):
    CONNECTING = "connecting"
    NEGOTIATING = "negotiating"
    LOGIN = "login"
    AUTHENTICATED = "authenticated"
    MENU = "menu"
    CHAT = "chat"
    BOARDS = "boards"
    FILES = "files"
    TRANSFER = "transfer"
    DISCONNECTING = "disconnecting"


class SessionTransport(Enum):
    """Transport type for the session - affects binary I/O handling"""
    TELNET = "telnet"  # Requires IAC escaping for binary data
    SSH = "ssh"        # Raw binary, no escaping needed


class ClientCapabilities:
    def __init__(self):
        self.ansi: bool = True
        self.color: bool = True
        self.ripscrip: bool = False
        self.binary: bool = False
        self.naws: bool = False
        self.echo: bool = False
        self.cols: int = 80
        self.rows: int = 24
        self.terminal_type: str = "unknown"
        self.encoding: str = "utf-8"
        self.seven_bit: bool = False  # For legacy 7-bit terminals
        self.xon_xoff: bool = False  # XON/XOFF flow control


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
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

    def __post_init__(self):
        if self.writer:
            # Force UTF-8 encoding on the telnetlib3 writer
            # The writer uses these attributes for encoding
            if hasattr(self.writer, 'encoding'):
                self.writer.encoding = 'utf-8'

            # Also check for the connection's encoding attribute
            if hasattr(self.writer, 'connection') and hasattr(self.writer.connection, 'encoding'):
                self.writer.connection.encoding = 'utf-8'

            peer = self.writer.transport.get_extra_info("peername")
            if peer:
                self.remote_addr = peer[0]
                self.remote_port = peer[1]

    async def negotiate(self) -> None:
        if not self.writer:
            return

        self.state = SessionState.NEGOTIATING
        logger.info(f"Session {self.id}: Starting telnet negotiation")

        # Negotiate 8-bit transparent transmission both ways
        # DO BINARY: request client to transmit in binary
        # WILL BINARY: advertise that server will transmit in binary
        self.writer.iac(DO, BINARY)
        self.writer.iac(WILL, BINARY)
        self.writer.iac(WILL, ECHO)
        self.writer.iac(DO, NAWS)
        self.writer.iac(DO, TTYPE)
        # Ensure the writer uses UTF-8 once binary mode is agreed
        try:
            if hasattr(self.writer, 'encoding'):
                self.writer.encoding = 'utf-8'
            if hasattr(self.writer, 'connection') and hasattr(self.writer.connection, 'encoding'):
                self.writer.connection.encoding = 'utf-8'
        except Exception:
            pass

        # Wait briefly for BINARY negotiation to complete before sending any
        # non-ASCII. telnetlib3 will encode as US-ASCII with replacement until
        # outbinary is True, which turns UTF-8 into question marks.
        outbinary = getattr(self.writer, 'outbinary', False)
        inbinary = getattr(self.writer, 'inbinary', False)
        waited = 0.0
        while not outbinary and waited < 2.0:
            await asyncio.sleep(0.05)
            waited += 0.05
            outbinary = getattr(self.writer, 'outbinary', False)
            inbinary = getattr(self.writer, 'inbinary', False)
        logger.info(
            f"Session {self.id}: BINARY negotiated (out={bool(outbinary)} in={bool(inbinary)}) after {waited:.2f}s"
        )

        if hasattr(self.writer, "naws"):
            naws_data = self.writer.get_extra_info("naws")
            if naws_data:
                self.capabilities.cols = naws_data[0]
                self.capabilities.rows = naws_data[1]
                self.capabilities.naws = True
                logger.info(f"Session {self.id}: NAWS {self.capabilities.cols}x{self.capabilities.rows}")

        if hasattr(self.writer, "ttype"):
            ttype = self.writer.get_extra_info("ttype")
            if ttype:
                self.capabilities.terminal_type = ttype.lower()
                logger.info(f"Session {self.id}: Terminal type: {self.capabilities.terminal_type}")

        await self.detect_ripscrip()

    async def detect_ripscrip(self) -> None:
        await self.write(b"\x1b[!|")
        await asyncio.sleep(0.2)

        try:
            data = await asyncio.wait_for(self.reader.read(100), timeout=0.5)
            # telnetlib3 returns strings, not bytes
            if "RIPTERM" in data or "RIPSCRIP" in data:
                self.capabilities.ripscrip = True
                logger.info(f"Session {self.id}: RIPscrip detected")
        except asyncio.TimeoutError:
            pass

    async def write(self, data: bytes | str) -> None:
        # Convert to string if bytes (for telnetlib3 compatibility)
        if isinstance(data, bytes):
            data = data.decode(self.capabilities.encoding, errors='replace')

        # telnetlib3's writer expects strings and handles encoding internally
        if self.writer:
            # Handle XON/XOFF flow control
            if self.capabilities.xon_xoff:
                # For flow control, we need to work with bytes
                encoded_data = data.encode(self.capabilities.encoding, errors='replace')
                # Apply 7-bit mask if needed
                if self.capabilities.seven_bit:
                    encoded_data = bytes(b & 0x7F for b in encoded_data)
                await self._write_with_flow_control(encoded_data)
            else:
                # telnetlib3's write method expects a string
                self.writer.write(data)
                await self.writer.drain()

        self.last_activity = datetime.now()

    async def _write_with_flow_control(self, data: bytes) -> None:
        """Write data with XON/XOFF flow control support"""
        XON = 0x11  # Ctrl-Q
        XOFF = 0x13  # Ctrl-S

        chunk_size = 256  # Send data in chunks
        paused = False

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            # telnetlib3's writer expects strings
            chunk_str = chunk.decode(self.capabilities.encoding, errors='replace')
            self.writer.write(chunk_str)
            await self.writer.drain()

            # Check for XOFF
            try:
                control = await asyncio.wait_for(self.reader.read(1), timeout=0.01)
                if control and control[0] == XOFF:
                    paused = True
                    logger.debug(f"Session {self.id}: XOFF received, pausing output")

                    # Wait for XON
                    while paused:
                        resume = await self.reader.read(1)
                        if resume and resume[0] == XON:
                            paused = False
                            logger.debug(f"Session {self.id}: XON received, resuming output")
                            break
            except asyncio.TimeoutError:
                pass

    async def writeline(self, text: str = "") -> None:
        await self.write(f"{text}\r\n")

    async def read(self, size: int = 1) -> str:
        if not self.reader:
            return ""

        # telnetlib3 returns Unicode strings when encoding is set on the server.
        # Avoid manual decoding here; rely on telnetlib3's codec.
        data = await self.reader.read(size)
        self.last_activity = datetime.now()
        return data or ""

    async def write_raw(self, data: bytes) -> None:
        """Write raw bytes directly to the transport (for binary file transfers).

        This bypasses string encoding and writes bytes directly, which is
        required for binary protocols like XMODEM, ZMODEM, and Kermit.

        For telnet sessions, IAC (0xFF) bytes are escaped as 0xFF 0xFF per
        telnet protocol. SSH sessions send raw bytes without escaping.
        """
        if not self.writer:
            return

        # Only escape IAC for telnet - SSH is a raw binary channel
        if self.transport_type == SessionTransport.TELNET:
            data = data.replace(b'\xff', b'\xff\xff')

        if hasattr(self.writer, 'transport') and self.writer.transport:
            self.writer.transport.write(data)
            if hasattr(self.writer, 'drain'):
                await self.writer.drain()
        elif hasattr(self.writer, 'write'):
            # SSH adapter - write directly
            self.writer.write(data)

        self.last_activity = datetime.now()

    async def read_raw(self, size: int, timeout: float = 10.0) -> Optional[bytes]:
        """Read raw bytes for binary file transfers.

        IMPORTANT LIMITATION: telnetlib3 with encoding='utf-8' decodes incoming
        data using UTF-8 with replacement. Binary data containing invalid UTF-8
        sequences will be corrupted (replaced with U+FFFD).

        For reliable binary transfers over telnet:
        - ZMODEM and Kermit use external binaries via PTY which bypasses this issue
        - XMODEM works for ASCII-safe files but may corrupt arbitrary binary data

        For SSH connections, the SSHReaderWriter provides true binary I/O via
        its read_raw() method.

        Returns None on timeout or if no data available.
        """
        if not self.reader:
            return None

        # Check if we have a direct read_raw method (SSH adapter provides this)
        if hasattr(self.reader, 'read_raw'):
            return await self.reader.read_raw(size, timeout)

        try:
            data = await asyncio.wait_for(
                self.reader.read(size),
                timeout=timeout
            )
            if data:
                self.last_activity = datetime.now()
                # Convert back to bytes using latin-1 (preserves byte values 0-255)
                # Note: This only works correctly if the data didn't contain
                # invalid UTF-8 sequences that were replaced during decoding
                return data.encode('latin-1', errors='replace') if isinstance(data, str) else data
            return None
        except asyncio.TimeoutError:
            return None

    async def readline(self, prompt: str = "", echo: bool = True, max_length: int = 255) -> str:
        if prompt:
            await self.write(prompt)

        buffer = []
        while True:
            char = await self.read(1)

            if not char:
                break

            if ord(char) == 13 or ord(char) == 10:
                await self.writeline()
                break

            elif ord(char) == 8 or ord(char) == 127:
                if buffer:
                    buffer.pop()
                    if echo:
                        await self.write(b"\x08 \x08")

            elif ord(char) >= 32 and len(buffer) < max_length:
                buffer.append(char)
                if echo:
                    await self.write(char)

        return "".join(buffer)

    async def read_password(self, prompt: str = "Password: ", max_length: int = 64) -> str:
        return await self.readline(prompt, echo=False, max_length=max_length)

    async def clear_screen(self) -> None:
        if self.capabilities.ansi:
            await self.write(b"\x1b[2J\x1b[H")
        else:
            await self.write(b"\r\n" * self.capabilities.rows)

    async def set_cursor(self, row: int, col: int) -> None:
        if self.capabilities.ansi:
            await self.write(f"\x1b[{row};{col}H")

    async def set_color(self, fg: Optional[int] = None, bg: Optional[int] = None, bold: bool = False) -> None:
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
            await self.write(f"\x1b[{';'.join(codes)}m")

    async def reset_color(self) -> None:
        if self.capabilities.ansi:
            await self.write(b"\x1b[0m")

    async def pause(self, message: str = "--More--") -> None:
        await self.write(f"\r\n{message}")
        await self.read(1)
        await self.write(f"\r{' ' * len(message)}\r")

    async def menu_select(self, options: list[tuple[str, str]], prompt: str = "Select: ") -> Optional[str]:
        for key, desc in options:
            await self.writeline(f"  [{key}] {desc}")

        while True:
            choice = (await self.readline(prompt)).upper()
            for key, _ in options:
                if choice == key.upper():
                    return key

            await self.writeline("Invalid selection. Please try again.")

    def t(self, key: str, **kwargs) -> str:
        """Translate a string using the session's current language"""
        return self.translator.get(key, **kwargs)

    def set_language(self, lang_code: str) -> bool:
        """Change the session's language"""
        if self.translator.set_language(lang_code):
            self.language = lang_code
            # Suggest appropriate encoding for Russian
            if lang_code == 'ru' and self.capabilities.encoding not in ['utf-8', 'windows-1251', 'koi8-r']:
                logger.info(f"Session {self.id}: Suggesting Russian-compatible encoding")
            return True
        return False

    async def disconnect(self) -> None:
        self.state = SessionState.DISCONNECTING
        logger.info(f"Session {self.id}: Disconnecting")

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        self.reader = None
        self.writer = None

    def is_authenticated(self) -> bool:
        return self.user_id is not None and self.state == SessionState.AUTHENTICATED

    def set_encoding(self, encoding: str) -> None:
        self.capabilities.encoding = encoding
        self.codec = CodecIO(encoding)

        # Update telnetlib3 writer encoding if it exists
        if self.writer:
            if hasattr(self.writer, 'encoding'):
                self.writer.encoding = encoding
            if hasattr(self.writer, 'connection') and hasattr(self.writer.connection, 'encoding'):
                self.writer.connection.encoding = encoding

        logger.info(f"Session {self.id}: Encoding set to {encoding}")

    def update_display_mode(self) -> None:
        """Update display mode based on current capabilities"""
        if self.capabilities.cols == 40:
            self.display_mode = DisplayMode.NARROW_ANSI if self.capabilities.ansi else DisplayMode.NARROW_PLAIN
        else:
            self.display_mode = DisplayMode.STANDARD_ANSI if self.capabilities.ansi else DisplayMode.STANDARD_PLAIN
        logger.info(f"Session {self.id}: Display mode set to {self.display_mode.value}")

    async def render_template(self, template_name: str, **context) -> None:
        """
        Render and display a template

        Args:
            template_name: Name of template (e.g., 'motd', 'menus/main')
            **context: Template context variables
        """
        if not self.template_engine:
            self.template_engine = TemplateEngine()

        # Add session context
        context.setdefault('username', self.username or 'Guest')
        context.setdefault('access_level', self.access_level)
        context.setdefault('last_login', self.last_activity.strftime("%Y-%m-%d %H:%M"))
        context.setdefault('session_time', self.get_session_time())

        # Render template
        content = await self.template_engine.render(
            template_name=template_name,
            context=context,
            display_mode=self.display_mode,
            encoding=self.capabilities.encoding,
            language=self.language
        )

        # Write to session
        await self.write(content)

    def get_session_time(self) -> str:
        """Get formatted session time"""
        delta = datetime.now() - self.connected_at
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
