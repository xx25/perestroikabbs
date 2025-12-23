"""
Stdio transport adapter for mgetty integration.

Provides a telnetlib3-compatible reader/writer interface for stdin/stdout,
enabling the BBS to run directly on a modem connection via mgetty.
"""
import asyncio
import sys
from typing import Optional

from .utils.logger import get_logger

logger = get_logger("stdio_transport")


class StdioWriteProtocol(asyncio.Protocol):
    """Simple protocol for stdout write pipe."""

    def __init__(self):
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport

    def connection_lost(self, exc):
        self._transport = None


class StdioReaderWriter:
    """Adapter providing telnetlib3-like reader/writer interface for stdio.

    This class wraps stdin/stdout as asyncio streams, providing the same
    interface as SSHReaderWriter for compatibility with the Session class.

    Key differences from telnet/SSH:
    - No protocol negotiation (raw TTY mode)
    - No IAC escaping (bytes pass through unchanged)
    - Terminal already configured by mgetty
    """

    def __init__(self, reader: asyncio.StreamReader, write_transport):
        self._reader = reader
        self._write_transport = write_transport
        self._char_buffer: str = ""
        self._raw_buffer: bytes = b""
        self._closed = False
        self._eof = False
        self._read_task: Optional[asyncio.Task] = None
        self._data_available = asyncio.Event()

    @classmethod
    async def create(cls) -> 'StdioReaderWriter':
        """Create a StdioReaderWriter connected to stdin/stdout.

        Uses asyncio's pipe APIs to wrap file descriptors for raw byte safety.
        """
        loop = asyncio.get_event_loop()

        # Create reader from stdin (fd 0) - use buffer for binary safety
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        # Create writer to stdout (fd 1) - use buffer for binary safety
        write_transport, _ = await loop.connect_write_pipe(
            StdioWriteProtocol, sys.stdout.buffer
        )

        instance = cls(reader, write_transport)
        instance._start_read_loop()
        return instance

    def _start_read_loop(self) -> None:
        """Start background task to read from stdin into buffers"""
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Continuously read from stdin into buffers"""
        try:
            while not self._closed:
                data = await self._reader.read(4096)
                if not data:
                    self._eof = True
                    self._data_available.set()
                    break

                # Add to raw buffer
                self._raw_buffer += data

                # Decode for character buffer (using latin-1 for byte transparency)
                # The Session will re-decode with the user's chosen encoding
                self._char_buffer += data.decode('latin-1')
                self._data_available.set()

        except Exception as e:
            logger.error(f"Read loop error: {e}")
            self._eof = True
            self._data_available.set()

    async def read(self, n: int = 1) -> str:
        """Read up to n characters (for text I/O).

        Returns empty string on EOF/close.
        """
        if self._closed or (self._eof and not self._char_buffer):
            return ""

        while not self._char_buffer and not self._closed and not self._eof:
            await self._data_available.wait()
            self._data_available.clear()

        if not self._char_buffer:
            return ""

        result = self._char_buffer[:n]
        self._char_buffer = self._char_buffer[n:]
        return result

    async def read_raw(self, n: int, timeout: float = 10.0) -> Optional[bytes]:
        """Read exactly n bytes of raw data (for binary transfers).

        Returns None on timeout or EOF.
        """
        if self._closed or (self._eof and not self._raw_buffer):
            return None

        start_time = asyncio.get_event_loop().time()

        while len(self._raw_buffer) < n:
            if self._closed or self._eof:
                return None

            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = timeout - elapsed
            if remaining <= 0:
                return None

            try:
                await asyncio.wait_for(
                    self._data_available.wait(),
                    timeout=remaining
                )
                self._data_available.clear()
            except asyncio.TimeoutError:
                return None

        result = self._raw_buffer[:n]
        self._raw_buffer = self._raw_buffer[n:]
        return result

    def write(self, data) -> None:
        """Write data to stdout.

        Accepts both str and bytes. Strings are encoded as latin-1
        (byte-transparent, matching telnet transport layer).
        """
        if self._closed:
            return

        if isinstance(data, str):
            data = data.encode('latin-1', errors='replace')

        self._write_transport.write(data)

    async def drain(self) -> None:
        """Flush the write buffer (no-op for pipe transport)"""
        # Pipe transports write synchronously to the OS, no buffering to drain
        pass

    def close(self) -> None:
        """Close the transport"""
        self._closed = True
        self._data_available.set()

        if self._read_task:
            self._read_task.cancel()

        if self._write_transport:
            self._write_transport.close()

    async def wait_closed(self) -> None:
        """Wait for close to complete (no-op for pipe transport)"""
        # Pipe transports close synchronously
        pass

    @property
    def transport(self):
        """Return transport-like object for raw I/O compatibility"""
        return StdioTransportAdapter(self._write_transport)


class StdioTransportAdapter:
    """Adapter for transport.write() compatibility with Session.write_raw()"""

    def __init__(self, write_transport):
        self._write_transport = write_transport

    def write(self, data: bytes) -> None:
        """Write raw bytes to stdout (no escaping needed for stdio)"""
        if isinstance(data, str):
            data = data.encode('latin-1', errors='replace')
        self._write_transport.write(data)

    def get_extra_info(self, name: str, default=None):
        """Compatibility method - returns placeholder for most queries"""
        if name == 'peername':
            # Return placeholder for modem connection
            return ('modem', 0)
        return default
