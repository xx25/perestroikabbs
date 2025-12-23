#!/usr/bin/env python3
"""
Stdio mode entry point for mgetty integration.

Usage in mgetty login.config:
    *    -    -    /path/to/python3 -m bbs.app.stdio_main

Environment variables available from mgetty:
    CALLER_ID   - Caller's phone number (if caller ID available)
    CALLER_NAME - Caller's name (if caller ID provides it)
    CALL_DATE   - Date of call
    CALL_TIME   - Time of call
    CALLED_ID   - Called number/MSN (for ISDN)
    CONNECT     - Connection speed/protocol (e.g., "CONNECT 14400/V.32bis")
    DEVICE      - TTY device name (e.g., "ttyS0")
    TERM        - Terminal type (if configured)
"""

import asyncio
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path

from .encoding import CharsetManager
from .session import Session, SessionState, SessionTransport
from .stdio_transport import StdioReaderWriter
from .storage.db import close_database, create_tables, init_database
from .ui.login import LoginUI
from .ui.menu import MainMenu
from .utils.config import load_config, get_config
from .utils.logger import setup_logging, get_logger


@dataclass
class MgettyInfo:
    """Container for mgetty environment information"""
    caller_id: str = ""       # CALLER_ID
    caller_name: str = ""     # CALLER_NAME
    call_date: str = ""       # CALL_DATE
    call_time: str = ""       # CALL_TIME
    called_id: str = ""       # CALLED_ID (ISDN/MSN)
    connect: str = ""         # CONNECT string (baud rate, protocol)
    device: str = ""          # DEVICE (ttyS0, etc.)
    term: str = ""            # TERM (terminal type)

    @classmethod
    def from_environment(cls) -> 'MgettyInfo':
        return cls(
            caller_id=os.environ.get('CALLER_ID', ''),
            caller_name=os.environ.get('CALLER_NAME', ''),
            call_date=os.environ.get('CALL_DATE', ''),
            call_time=os.environ.get('CALL_TIME', ''),
            called_id=os.environ.get('CALLED_ID', ''),
            connect=os.environ.get('CONNECT', ''),
            device=os.environ.get('DEVICE', ''),
            term=os.environ.get('TERM', ''),
        )


logger = None  # Will be initialized after setup_logging()


async def run_bbs_session(adapter: StdioReaderWriter, mgetty_info: MgettyInfo, charset_manager: CharsetManager) -> None:
    """Run a single BBS session on stdio"""
    session = Session(
        reader=adapter,
        writer=adapter,
        transport_type=SessionTransport.STDIO,
    )

    # Set initial capabilities for modem connection
    session.capabilities.binary = True
    session.capabilities.ansi = True  # Most terminal emulators support ANSI
    session.capabilities.echo = True

    # Store mgetty info for logging/display
    session.data['mgetty'] = mgetty_info

    # Use caller ID as remote address if available
    if mgetty_info.caller_id:
        session.remote_addr = mgetty_info.caller_id
    elif mgetty_info.device:
        session.remote_addr = f"modem:{mgetty_info.device}"
    else:
        session.remote_addr = "modem"

    logger.info(
        f"Stdio session started: CallerID={mgetty_info.caller_id or 'unknown'}, "
        f"Connect={mgetty_info.connect or 'unknown'}, Device={mgetty_info.device or 'unknown'}"
    )

    try:
        # Transition session state to LOGIN (skips telnet negotiation for STDIO)
        await session.negotiate()

        # Check for RIPscrip terminal (some modem users have RIPterm)
        await session.detect_ripscrip()

        # Run login UI (charset/language selection, auth)
        login_ui = LoginUI(session, charset_manager)
        authenticated = await login_ui.run()

        if authenticated:
            session.state = SessionState.AUTHENTICATED
            menu = MainMenu(session)
            await menu.run()
        else:
            await session.writeline("\r\nGoodbye!")

    except asyncio.CancelledError:
        logger.info("Stdio session cancelled")
    except Exception as e:
        logger.error(f"Stdio session error: {e}", exc_info=True)
    finally:
        await session.disconnect()
        logger.info("Stdio session ended")


async def main_async() -> None:
    """Main async entry point for stdio mode"""
    global logger
    logger = get_logger("stdio_main")

    config_path = os.environ.get('BBS_CONFIG', 'config.toml')

    if not Path(config_path).exists() and Path("config.example.toml").exists():
        logger.warning(f"Config file '{config_path}' not found. Using example config.")
        config_path = "config.example.toml"

    config = load_config(config_path)
    logger.info(f"Configuration loaded from {config_path}")

    # Initialize database
    logger.info("Initializing database...")
    await init_database()
    await create_tables()

    # Create charset manager
    charset_manager = CharsetManager(config.charset.supported_encodings)

    # Capture mgetty environment
    mgetty_info = MgettyInfo.from_environment()

    # Create stdio adapter
    adapter = await StdioReaderWriter.create()

    # Setup signal handlers
    shutdown_event = asyncio.Event()

    def signal_handler(sig):
        logger.info(f"Received signal {sig}")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    # Run session with shutdown capability
    session_task = asyncio.create_task(run_bbs_session(adapter, mgetty_info, charset_manager))
    shutdown_task = asyncio.create_task(shutdown_event.wait())

    done, pending = await asyncio.wait(
        [session_task, shutdown_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Cancel pending tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Cleanup
    await close_database()
    adapter.close()
    await adapter.wait_closed()

    logger.info("Stdio mode shutdown complete")


def main() -> None:
    """Synchronous entry point"""
    setup_logging()
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        if logger:
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
