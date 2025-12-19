"""
SSH Gateway for Perestroika BBS
Provides SSH access to the BBS system by bridging SSH to the BBS session
"""
import asyncio
from typing import Optional

import asyncssh
from asyncssh import SSHServerConnection, SSHServerSession

from .session import Session, SessionState, SessionTransport, ClientCapabilities
from .storage.repositories import UserRepository
from .ui.login import LoginUI
from .ui.menu import MainMenu
from .encoding import CharsetManager
from .utils.config import get_config
from .utils.logger import get_logger

logger = get_logger("ssh_gateway")


class SSHReaderWriter:
    """Adapter that provides telnetlib3-like reader/writer interface for SSH channels.

    With encoding=None on the SSH server, we receive raw bytes. This adapter
    maintains both a text buffer (for UI) and a raw buffer (for binary transfers).
    """

    def __init__(self, channel):
        self._channel = channel
        self._char_buffer: str = ""  # Buffer for character-by-character reading
        self._raw_buffer: bytes = b""  # Buffer for raw binary reading
        self._data_available = asyncio.Event()
        self._eof_received = False
        self._closed = False

    async def read(self, n: int = 1) -> str:
        """Read up to n characters from the SSH channel.

        Blocks until data is available. Returns empty string only on
        true EOF or close (matching telnetlib3 behavior). Callers needing
        timeouts should use asyncio.wait_for().
        """
        # Immediate EOF check
        if self._closed or (self._eof_received and not self._char_buffer):
            return ""

        # Block until we have data OR EOF/close occurs
        while not self._char_buffer and not self._closed and not self._eof_received:
            await self._data_available.wait()
            self._data_available.clear()

        # After waiting: if still no data, must be EOF/close
        if not self._char_buffer:
            return ""

        # Return up to n characters
        result = self._char_buffer[:n]
        self._char_buffer = self._char_buffer[n:]
        return result

    def write(self, data) -> None:
        """Write data to the SSH channel"""
        if self._closed:
            return
        # Channel expects bytes when encoding=None
        if isinstance(data, str):
            data = data.encode('utf-8', errors='replace')
        self._channel.write(data)

    async def drain(self) -> None:
        """Drain is a no-op for SSH - writes are immediate"""
        pass

    def close(self) -> None:
        """Close the channel"""
        self._closed = True
        self._data_available.set()  # Wake up any waiting readers
        self._channel.close()

    async def wait_closed(self) -> None:
        """Wait for channel to close"""
        pass

    def set_eof(self) -> None:
        """Signal that EOF has been received"""
        self._eof_received = True
        self._data_available.set()

    def feed_data(self, data: bytes) -> None:
        """Feed raw data into buffers.

        With encoding=None, SSH delivers bytes. We decode for text buffer
        and keep raw for binary buffer.
        """
        if self._closed:
            return
        # Add to raw buffer as-is
        self._raw_buffer += data
        # Decode for text buffer (UTF-8 for display)
        self._char_buffer += data.decode('utf-8', errors='replace')
        self._data_available.set()

    async def read_raw(self, n: int, timeout: float = 10.0) -> Optional[bytes]:
        """Read exactly n bytes of raw binary data from the buffer.

        For binary protocols that require exact block sizes (e.g., XMODEM).
        Returns None on timeout or EOF without consuming partial data.
        Partial data remains buffered for the next call.
        """
        if self._closed or (self._eof_received and not self._raw_buffer):
            return None

        start_time = asyncio.get_event_loop().time()
        while len(self._raw_buffer) < n:
            if self._closed or self._eof_received:
                # EOF/close with insufficient data - return None, keep partial buffered
                return None
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = timeout - elapsed
            if remaining <= 0:
                # Timeout with insufficient data - return None, keep partial buffered
                return None
            try:
                await asyncio.wait_for(self._data_available.wait(), timeout=remaining)
                self._data_available.clear()
            except asyncio.TimeoutError:
                # Timeout - return None, partial data stays buffered
                return None

        # Have at least n bytes - consume and return exactly n
        result = self._raw_buffer[:n]
        self._raw_buffer = self._raw_buffer[n:]
        return result

    @property
    def transport(self):
        """Return a transport-like object for raw I/O"""
        return SSHTransportAdapter(self._channel)


class SSHTransportAdapter:
    """Adapter to provide transport.write() for raw binary I/O"""

    def __init__(self, channel):
        self._channel = channel

    def write(self, data: bytes) -> None:
        """Write raw bytes to the channel.

        With encoding=None, the channel expects bytes directly.
        """
        if isinstance(data, str):
            data = data.encode('utf-8', errors='replace')
        self._channel.write(data)

    def get_extra_info(self, name: str, default=None):
        """Get extra info from the channel"""
        return self._channel.get_extra_info(name, default)


class BBSSSHSession(SSHServerSession):
    """SSH session that bridges to the BBS core"""

    def __init__(self, server: 'BBSSSHServer', username: str):
        self._server = server
        self._username = username
        self._channel = None
        self._session: Optional[Session] = None
        self._bbs_task: Optional[asyncio.Task] = None
        self._adapter: Optional[SSHReaderWriter] = None

    def connection_made(self, chan) -> None:
        """Called when SSH channel is established"""
        self._channel = chan
        logger.info(f"SSH session started for user {self._username}")

    def shell_requested(self) -> bool:
        """Called when client requests a shell"""
        return True

    def session_started(self) -> None:
        """Called when the session starts - launch the BBS"""
        self._adapter = SSHReaderWriter(self._channel)
        self._bbs_task = asyncio.create_task(self._run_bbs_session())

    async def _run_bbs_session(self) -> None:
        """Run the BBS session for this SSH connection"""
        try:
            # Create a Session with our SSH adapter
            self._session = Session(
                reader=self._adapter,
                writer=self._adapter,
                transport_type=SessionTransport.SSH,
            )

            # Set up SSH-specific capabilities
            self._session.capabilities.binary = True
            self._session.capabilities.ansi = True
            self._session.capabilities.echo = True

            # Get terminal size if available
            term_size = self._channel.get_terminal_size()
            if term_size:
                self._session.capabilities.cols = term_size[0]
                self._session.capabilities.rows = term_size[1]
                self._session.capabilities.naws = True

            # Pre-authenticate with the SSH username
            user_repo = UserRepository()
            user = await user_repo.get_by_username(self._username)
            if user:
                self._session.user_id = user.id
                self._session.username = user.username
                self._session.access_level = user.access_level
                self._session.state = SessionState.AUTHENTICATED

                await self._session.writeline(f"\r\nWelcome, {self._username}!")
                await asyncio.sleep(0.5)

                # Go directly to main menu since SSH already authenticated
                menu = MainMenu(self._session)
                await menu.run()
            else:
                await self._session.writeline("\r\nUser not found. Goodbye!")

        except asyncio.CancelledError:
            logger.info(f"SSH session {self._username} cancelled")
        except Exception as e:
            logger.error(f"SSH session error for {self._username}: {e}", exc_info=True)
        finally:
            if self._session:
                await self._session.disconnect()
            self._channel.exit(0)

    def data_received(self, data: bytes, datatype) -> None:
        """Handle data received from SSH client.

        With encoding=None, data is always bytes.
        """
        if self._adapter:
            self._adapter.feed_data(data)

    def eof_received(self) -> bool:
        """Called when EOF is received"""
        logger.info(f"SSH EOF received for {self._username}")
        if self._adapter:
            self._adapter.set_eof()
        return False

    def terminal_size_changed(self, width: int, height: int, pixwidth: int, pixheight: int) -> None:
        """Handle terminal resize"""
        if self._session:
            self._session.capabilities.cols = width
            self._session.capabilities.rows = height
            logger.debug(f"SSH terminal resized to {width}x{height}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Clean up when connection is lost"""
        logger.info(f"SSH session ended for {self._username}")
        if self._bbs_task and not self._bbs_task.done():
            self._bbs_task.cancel()


class BBSSSHServer(asyncssh.SSHServer):
    """SSH server that creates BBS sessions"""

    def __init__(self, config):
        self.config = config
        self.user_repo = UserRepository()
        self._conn = None
        self._authenticated_user: Optional[str] = None

    def connection_made(self, conn: SSHServerConnection) -> None:
        """Called when an SSH connection is made"""
        self._conn = conn
        peername = conn.get_extra_info('peername')
        logger.info(f"SSH connection from {peername}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when connection is lost"""
        if exc:
            logger.error(f"SSH connection lost: {exc}")

    def password_auth_supported(self) -> bool:
        """Enable password authentication"""
        return True

    async def validate_password(self, username: str, password: str) -> bool:
        """Validate user credentials"""
        try:
            # Use the user repository to validate
            user = await self.user_repo.get_by_username(username)
            if user:
                # Verify password using the same method as telnet login
                from argon2 import PasswordHasher
                ph = PasswordHasher()
                try:
                    ph.verify(user.password_hash, password)
                    self._authenticated_user = username
                    return True
                except Exception:
                    pass
            return False
        except Exception as e:
            logger.error(f"Error validating SSH password: {e}")
            return False

    def begin_auth(self, username: str) -> bool:
        """Called at the start of authentication - store the username"""
        self._authenticated_user = None
        return True

    def session_requested(self) -> Optional[BBSSSHSession]:
        """Called when a session is requested"""
        if not self._authenticated_user:
            logger.warning("Session requested without authenticated user")
            return None
        return BBSSSHSession(self, self._authenticated_user)


async def start_ssh_server(config):
    """Start the SSH server"""
    try:
        # Load or generate SSH host keys
        ssh_host_keys = []
        key_path = config.get('ssh', {}).get('host_key', '/var/lib/bbs/ssh_host_key')

        try:
            ssh_host_keys = [key_path]
        except:
            # Generate a new key if not found
            logger.info("Generating new SSH host key...")
            import subprocess
            subprocess.run(['ssh-keygen', '-t', 'rsa', '-b', '2048', '-N', '', '-f', key_path],
                         check=True, capture_output=True)
            ssh_host_keys = [key_path]

        # Start SSH server
        port = config.get('ssh', {}).get('port', 2222)
        host = config.get('ssh', {}).get('host', '0.0.0.0')

        await asyncssh.create_server(
            lambda: BBSSSHServer(config),
            host, port,
            server_host_keys=ssh_host_keys,
            process_factory=None,  # We handle sessions ourselves
            encoding=None  # Raw binary mode for true 8-bit clean transfers
        )

        logger.info(f"SSH server listening on {host}:{port}")

    except Exception as e:
        logger.error(f"Failed to start SSH server: {e}")
        raise


def integrate_ssh_gateway(app_config):
    """
    Integrate SSH gateway with the main BBS application

    This should be called from the main application startup
    """
    if app_config.get('ssh', {}).get('enabled', False):
        logger.info("SSH gateway enabled, starting SSH server...")
        asyncio.create_task(start_ssh_server(app_config))
    else:
        logger.info("SSH gateway disabled in configuration")