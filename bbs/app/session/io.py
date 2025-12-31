"""
Session I/O operations.

Handles all network I/O including text encoding/decoding and binary transfers.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from telnetlib3 import TelnetReader, TelnetWriter, DO, WILL, BINARY, ECHO, NAWS, TTYPE

from ..encoding import CodecIO
from ..utils.logger import get_logger
from .state import SessionData, SessionState, SessionTransport, ClientCapabilities

if TYPE_CHECKING:
    pass

logger = get_logger("session.io")


@dataclass
class SessionIO:
    """
    Handles all I/O operations for a session.

    This includes text encoding/decoding, binary transfers, and protocol negotiation.
    """

    reader: Optional[TelnetReader] = None
    writer: Optional[TelnetWriter] = None
    codec: CodecIO = field(default_factory=lambda: CodecIO("utf-8"))
    _input_buffer: str = ""
    _output_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    # Reference to state for updating activity and reading transport type
    _state: Optional[SessionData] = None

    @property
    def transport_type(self) -> SessionTransport:
        """Get transport type from state."""
        if self._state:
            return self._state.transport_type
        return SessionTransport.TELNET

    @property
    def capabilities(self) -> ClientCapabilities:
        """Get capabilities from state."""
        if self._state:
            return self._state.capabilities
        return ClientCapabilities()

    def _update_activity(self) -> None:
        """Update last activity timestamp on state."""
        if self._state:
            self._state.update_activity()

    async def negotiate(self) -> None:
        """Perform telnet protocol negotiation."""
        if not self.writer or not self._state:
            return

        # Skip telnet negotiation for non-telnet transports
        if self.transport_type != SessionTransport.TELNET:
            self._state.state = SessionState.LOGIN
            return

        self._state.state = SessionState.NEGOTIATING
        logger.info(f"Session {self._state.id}: Starting telnet negotiation")

        # Negotiate 8-bit transparent transmission both ways
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
            f"Session {self._state.id}: BINARY negotiated (out={bool(outbinary)} in={bool(inbinary)}) after {waited:.2f}s"
        )

        if hasattr(self.writer, "naws"):
            naws_data = self.writer.get_extra_info("naws")
            if naws_data:
                self.capabilities.cols = naws_data[0]
                self.capabilities.rows = naws_data[1]
                self.capabilities.naws = True
                logger.info(f"Session {self._state.id}: NAWS {self.capabilities.cols}x{self.capabilities.rows}")

        if hasattr(self.writer, "ttype"):
            ttype = self.writer.get_extra_info("ttype")
            if ttype:
                self.capabilities.terminal_type = ttype.lower()
                logger.info(f"Session {self._state.id}: Terminal type: {self.capabilities.terminal_type}")

        await self.detect_ripscrip()

    async def detect_ripscrip(self) -> None:
        """Detect RIPscrip capability."""
        if not self.reader or not self._state:
            return

        await self.write(b"\x1b[!|")
        await asyncio.sleep(0.2)

        try:
            data = await asyncio.wait_for(self.reader.read(100), timeout=0.5)
            if "RIPTERM" in data or "RIPSCRIP" in data:
                self.capabilities.ripscrip = True
                logger.info(f"Session {self._state.id}: RIPscrip detected")
        except asyncio.TimeoutError:
            pass

    async def write(self, data: bytes | str) -> None:
        """
        Write text data with proper encoding.

        For text output only. Binary transfers must use write_raw().
        """
        if not self.writer:
            return

        if self.transport_type == SessionTransport.SSH:
            # SSH: writer handles UTF-8 encoding, pass strings directly
            if isinstance(data, bytes):
                data = data.decode(self.capabilities.encoding, errors='replace')
            # Apply transliteration for 7-bit mode (converts Cyrillic to Latin)
            if self.capabilities.seven_bit:
                from ..i18n.translit import transliterate
                data = transliterate(data)
            self.writer.write(data)
            await self.writer.drain()
        else:
            # Telnet: use latin-1 byte-transparent transport
            if isinstance(data, str):
                # Apply transliteration for 7-bit mode (converts Cyrillic to Latin)
                if self.capabilities.seven_bit:
                    from ..i18n.translit import transliterate
                    data = transliterate(data)
                data_bytes = data.encode(self.capabilities.encoding, errors='replace')
            else:
                data_bytes = data

            # Apply 7-bit mask if needed (safety fallback)
            if self.capabilities.seven_bit:
                data_bytes = bytes(b & 0x7F for b in data_bytes)

            if self.capabilities.xon_xoff:
                await self._write_with_flow_control(data_bytes)
            else:
                transport_str = data_bytes.decode('latin-1')
                self.writer.write(transport_str)
                await self.writer.drain()

        self._update_activity()

    async def _write_with_flow_control(self, data: bytes) -> None:
        """Write data with XON/XOFF flow control support."""
        if not self.writer or not self.reader:
            return

        XON = 0x11  # Ctrl-Q
        XOFF = 0x13  # Ctrl-S
        chunk_size = 256
        paused = False

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            chunk_str = chunk.decode('latin-1')
            self.writer.write(chunk_str)
            await self.writer.drain()

            try:
                control = await asyncio.wait_for(self.reader.read(1), timeout=0.01)
                if control:
                    control_byte = ord(control)
                    if control_byte == XOFF:
                        paused = True
                        logger.debug(f"Session: XOFF received, pausing output")

                        while paused:
                            resume = await self.reader.read(1)
                            if resume and ord(resume) == XON:
                                paused = False
                                logger.debug(f"Session: XON received, resuming output")
                                break
            except asyncio.TimeoutError:
                pass

    async def writeline(self, text: str = "") -> None:
        """Write text followed by CRLF."""
        await self.write(f"{text}\r\n")

    async def read(self, size: int = 1) -> str:
        """Read text with proper decoding."""
        if not self.reader:
            return ""

        raw = await self.reader.read(size)
        if not raw:
            return ""

        self._update_activity()

        if self.transport_type == SessionTransport.SSH:
            return raw
        else:
            raw_bytes = raw.encode('latin-1', errors='replace')
            return raw_bytes.decode(self.capabilities.encoding, errors='replace')

    async def write_raw(self, data: bytes) -> None:
        """
        Write raw bytes directly to the transport (for binary file transfers).

        For telnet sessions, IAC (0xFF) bytes are escaped as 0xFF 0xFF.
        SSH and STDIO sessions send raw bytes without escaping.
        """
        if not self.writer:
            return

        if self.transport_type == SessionTransport.TELNET:
            data = data.replace(b'\xff', b'\xff\xff')

        if hasattr(self.writer, 'transport') and self.writer.transport:
            self.writer.transport.write(data)
            if hasattr(self.writer, 'drain'):
                await self.writer.drain()
        elif hasattr(self.writer, 'write'):
            self.writer.write(data)

        self._update_activity()

    async def read_raw(self, size: int, timeout: float = 10.0) -> Optional[bytes]:
        """
        Read raw bytes for binary file transfers.

        Returns None on timeout or if no data available.
        """
        if not self.reader:
            return None

        if hasattr(self.reader, 'read_raw'):
            return await self.reader.read_raw(size, timeout)

        try:
            data = await asyncio.wait_for(self.reader.read(size), timeout=timeout)
            if data:
                self._update_activity()
                return data.encode('latin-1') if isinstance(data, str) else data
            return None
        except asyncio.TimeoutError:
            return None

    async def readline(self, prompt: str = "", echo: bool = True, max_length: int = 255) -> str:
        """Read a line of input with proper encoding support."""
        if not self.reader:
            return ""

        if prompt:
            await self.write(prompt)

        if self.transport_type == SessionTransport.SSH:
            char_buffer = []
            while True:
                char = await self.reader.read(1)
                if not char:
                    break

                self._update_activity()

                if char in ('\r', '\n'):
                    await self.writeline()
                    break
                elif char in ('\x08', '\x7f'):
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
            byte_buffer = bytearray()
            while True:
                raw = await self.reader.read(1)
                if not raw:
                    break

                byte_val = ord(raw)
                self._update_activity()

                if byte_val == 13 or byte_val == 10:
                    await self.writeline()
                    break
                elif byte_val == 8 or byte_val == 127:
                    if byte_buffer:
                        byte_buffer.pop()
                        if echo:
                            await self.write(b"\x08 \x08")
                elif byte_val >= 32 and len(byte_buffer) < max_length:
                    byte_buffer.append(byte_val)
                    if echo and self.writer:
                        self.writer.write(raw)
                        await self.writer.drain()

            return bytes(byte_buffer).decode(self.capabilities.encoding, errors='replace')

    async def read_password(self, prompt: str = "Password: ", max_length: int = 64) -> str:
        """Read password input without echo."""
        return await self.readline(prompt, echo=False, max_length=max_length)

    async def disconnect(self) -> None:
        """Disconnect the session."""
        if self._state:
            self._state.state = SessionState.DISCONNECTING
            logger.info(f"Session {self._state.id}: Disconnecting")

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        self.reader = None
        self.writer = None

    def set_encoding(self, encoding: str) -> None:
        """
        Set the session's character encoding.

        This affects how text is encoded/decoded at the application layer.
        """
        if self._state:
            self._state.capabilities.encoding = encoding
        self.codec = CodecIO(encoding)
        if self._state:
            logger.info(f"Session {self._state.id}: Encoding set to {encoding}")
