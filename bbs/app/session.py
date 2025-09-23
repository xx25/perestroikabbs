import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from telnetlib3 import TelnetReader, TelnetWriter

from .encoding import CodecIO
from .utils.logger import get_logger

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
    user_id: Optional[int] = None
    username: Optional[str] = None
    access_level: int = 0
    capabilities: ClientCapabilities = field(default_factory=ClientCapabilities)
    codec: CodecIO = field(default_factory=lambda: CodecIO("utf-8"))
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    remote_addr: Optional[str] = None
    remote_port: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    _input_buffer: str = ""
    _output_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

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

        self.writer.iac(telnetlib3.DO, telnetlib3.BINARY)
        self.writer.iac(telnetlib3.WILL, telnetlib3.ECHO)
        self.writer.iac(telnetlib3.DO, telnetlib3.NAWS)
        self.writer.iac(telnetlib3.DO, telnetlib3.TTYPE)

        await asyncio.sleep(0.5)

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
            if b"RIPTERM" in data or b"RIPSCRIP" in data:
                self.capabilities.ripscrip = True
                logger.info(f"Session {self.id}: RIPscrip detected")
        except asyncio.TimeoutError:
            pass

    async def write(self, data: bytes | str) -> None:
        if isinstance(data, str):
            data = self.codec.encode(data)

        # Apply 7-bit mask if needed
        if self.capabilities.seven_bit:
            data = bytes(b & 0x7F for b in data)

        if self.writer:
            # Handle XON/XOFF flow control
            if self.capabilities.xon_xoff:
                await self._write_with_flow_control(data)
            else:
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
            self.writer.write(chunk)
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

        data = await self.reader.read(size)
        self.last_activity = datetime.now()
        return self.codec.decode(data) if data else ""

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
        logger.info(f"Session {self.id}: Encoding set to {encoding}")