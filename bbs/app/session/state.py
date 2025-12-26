"""
Session state management.

Contains pure data/state for a BBS session without I/O dependencies.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class SessionState(Enum):
    """Session lifecycle states."""

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
    """Transport type for the session - affects binary I/O handling."""

    TELNET = "telnet"  # Requires IAC escaping for binary data
    SSH = "ssh"  # Raw binary, no escaping needed
    STDIO = "stdio"  # Raw binary via stdin/stdout (mgetty)


class ClientCapabilities:
    """Client terminal capabilities detected during negotiation."""

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
class SessionData:
    """
    Pure state container for session data.

    This class holds only data and simple queries, with no I/O dependencies.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.CONNECTING
    transport_type: SessionTransport = SessionTransport.TELNET
    user_id: Optional[int] = None
    username: Optional[str] = None
    access_level: int = 0
    language: str = "en"
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    remote_addr: Optional[str] = None
    remote_port: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    capabilities: ClientCapabilities = field(default_factory=ClientCapabilities)

    def is_authenticated(self) -> bool:
        """Check if the session is authenticated."""
        return self.user_id is not None and self.state == SessionState.AUTHENTICATED

    def get_session_time(self) -> str:
        """Get formatted session duration as HH:MM:SS."""
        delta = datetime.now() - self.connected_at
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()
