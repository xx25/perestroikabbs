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

        # Wait briefly for BINARY negotiation to complete
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
            # telnetlib3 returns latin-1 strings; ASCII keywords preserved
            if "RIPTERM" in data or "RIPSCRIP" in data:
                self.capabilities.ripscrip = True
                logger.info(f"Session {self.id}: RIPscrip detected")
        except asyncio.TimeoutError:
            pass

    async def write(self, data: bytes | str) -> None:
        """Write text data with proper encoding.

        For text output only. Binary transfers must use write_raw().

        Args:
            data: String to write (will be encoded with session encoding),
                  or bytes already encoded in session encoding.
        """
        if not self.writer:
            return

        if self.transport_type == SessionTransport.SSH:
            # SSH: writer handles UTF-8 encoding, pass strings directly
            if isinstance(data, bytes):
                data = data.decode(self.capabilities.encoding, errors='replace')
            self.writer.write(data)
            await self.writer.drain()
        else:
            # Telnet: use latin-1 byte-transparent transport
            if isinstance(data, str):
                data_bytes = data.encode(self.capabilities.encoding, errors='replace')
            else:
                data_bytes = data

            # Apply 7-bit mask if needed
            if self.capabilities.seven_bit:
                data_bytes = bytes(b & 0x7F for b in data_bytes)

            if self.capabilities.xon_xoff:
                await self._write_with_flow_control(data_bytes)
            else:
                # Convert to latin-1 string for telnetlib3
                transport_str = data_bytes.decode('latin-1')
                self.writer.write(transport_str)
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
            # Use latin-1 for byte-transparent transport
            chunk_str = chunk.decode('latin-1')
            self.writer.write(chunk_str)
            await self.writer.drain()

            # Check for XOFF (read raw byte via latin-1 transport)
            try:
                control = await asyncio.wait_for(self.reader.read(1), timeout=0.01)
                if control:
                    # Convert latin-1 char back to byte value
                    control_byte = ord(control)
                    if control_byte == XOFF:
                        paused = True
                        logger.debug(f"Session {self.id}: XOFF received, pausing output")

                        # Wait for XON
                        while paused:
                            resume = await self.reader.read(1)
                            if resume and ord(resume) == XON:
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

        raw = await self.reader.read(size)
        if not raw:
            return ""

        self.last_activity = datetime.now()

        if self.transport_type == SessionTransport.SSH:
            # SSH: reader already returns Unicode (UTF-8 decoded)
            return raw
        else:
            # Telnet: latin-1 transport, re-encode to bytes then decode with session encoding
            raw_bytes = raw.encode('latin-1', errors='replace')
            return raw_bytes.decode(self.capabilities.encoding, errors='replace')

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

        Uses the latin-1 transport layer which is byte-transparent, so all
        byte values 0x00-0xFF are preserved without corruption.

        For SSH connections, the SSHReaderWriter provides its own read_raw()
        method which is used instead.

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
                # Convert latin-1 string back to bytes (byte-transparent)
                return data.encode('latin-1') if isinstance(data, str) else data
            return None
        except asyncio.TimeoutError:
            return None

    async def readline(self, prompt: str = "", echo: bool = True, max_length: int = 255) -> str:
        """Read a line of input with proper encoding support."""
        if prompt:
            await self.write(prompt)

        if self.transport_type == SessionTransport.SSH:
            # SSH: reader returns Unicode chars, build string directly
            char_buffer = []
            while True:
                char = await self.reader.read(1)
                if not char:
                    break

                self.last_activity = datetime.now()

                if char in ('\r', '\n'):
                    await self.writeline()
                    break
                elif char in ('\x08', '\x7f'):  # BS or DEL
                    if char_buffer:
                        char_buffer.pop()
                        if echo:
                            await self.write("\x08 \x08")
                elif ord(char) >= 32 and len(char_buffer) < max_length:
                    char_buffer.append(char)
                    if echo:
                        await self.write(char)

            return "".join(char_buffer)
        else:
            # Telnet: read raw bytes via latin-1, buffer and decode at end
            byte_buffer = bytearray()
            while True:
                raw = await self.reader.read(1)
                if not raw:
                    break

                byte_val = ord(raw)
                self.last_activity = datetime.now()

                if byte_val == 13 or byte_val == 10:  # CR or LF
                    await self.writeline()
                    break
                elif byte_val == 8 or byte_val == 127:  # BS or DEL
                    if byte_buffer:
                        byte_buffer.pop()
                        if echo:
                            await self.write(b"\x08 \x08")
                elif byte_val >= 32 and len(byte_buffer) < max_length:
                    byte_buffer.append(byte_val)
                    if echo:
                        # Echo byte back via latin-1 transport
                        if self.writer:
                            self.writer.write(raw)
                            await self.writer.drain()

            return bytes(byte_buffer).decode(self.capabilities.encoding, errors='replace')

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
        """Set the session's character encoding.

        This affects how text is encoded/decoded at the application layer.
        The transport layer always uses latin-1 (byte-transparent).
        """
        self.capabilities.encoding = encoding
        self.codec = CodecIO(encoding)
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
