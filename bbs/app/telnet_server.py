import asyncio
from typing import Dict, Optional

import telnetlib3

from .encoding import CharsetManager
from .session import Session, SessionState
from .ui.login import LoginUI
from .ui.menu import MainMenu
from .utils.config import get_config
from .utils.logger import get_logger

logger = get_logger("telnet")


class TelnetServer:
    def __init__(self):
        self.config = get_config()
        self.sessions: Dict[str, Session] = {}
        self.charset_manager = CharsetManager(self.config.charset.supported_encodings)
        self._server: Optional[asyncio.Server] = None
        self._running = False

    async def shell(self, reader: telnetlib3.TelnetReader, writer: telnetlib3.TelnetWriter) -> None:
        session = Session(reader=reader, writer=writer)
        self.sessions[session.id] = session

        logger.info(f"New connection from {session.remote_addr}:{session.remote_port} (Session: {session.id})")

        try:
            await session.negotiate()

            # Don't show MOTD yet - let user configure charset/language first
            login_ui = LoginUI(session, self.charset_manager)

            # LoginUI will handle charset, language, terminal setup first
            # Then show MOTD with proper encoding
            authenticated = await login_ui.run()

            if authenticated:
                session.state = SessionState.AUTHENTICATED
                await session.writeline(f"\r\nWelcome back, {session.username}!")
                await asyncio.sleep(1)

                menu = MainMenu(session)
                await menu.run()
            else:
                await session.writeline("\r\nGoodbye!")

        except asyncio.CancelledError:
            logger.info(f"Session {session.id} cancelled")
        except Exception as e:
            logger.error(f"Session {session.id} error: {e}", exc_info=True)
            await session.writeline("\r\nAn error occurred. Disconnecting...")
        finally:
            await session.disconnect()
            del self.sessions[session.id]
            logger.info(f"Session {session.id} ended")

    async def show_motd(self, session: Session) -> None:
        await session.clear_screen()

        motd_file = self.config.server.motd_asset
        try:
            from pathlib import Path
            motd_path = Path(__file__).parent / "assets" / motd_file

            if motd_path.exists():
                with open(motd_path, "rb") as f:
                    content = f.read()

                if session.capabilities.encoding == "cp437" or "437" in session.capabilities.encoding:
                    await session.write(content)
                else:
                    await session.write(content.decode("utf-8", errors="replace"))
            else:
                await self.show_default_motd(session)
        except Exception as e:
            logger.warning(f"Could not load MOTD: {e}")
            await self.show_default_motd(session)

        await session.writeline()

    async def show_default_motd(self, session: Session) -> None:
        if session.capabilities.ansi:
            await session.set_color(fg=6, bold=True)
            await session.writeline("╔══════════════════════════════════════════════╗")
            await session.writeline("║                                              ║")
            await session.writeline("║         PERESTROIKA BBS SYSTEM               ║")
            await session.writeline("║                                              ║")
            await session.writeline("║         A Modern Retro Experience            ║")
            await session.writeline("║                                              ║")
            await session.writeline("╚══════════════════════════════════════════════╝")
            await session.reset_color()
        else:
            await session.writeline("=" * 50)
            await session.writeline("         PERESTROIKA BBS SYSTEM")
            await session.writeline("         A Modern Retro Experience")
            await session.writeline("=" * 50)

        await session.writeline()
        await session.writeline(self.config.server.welcome_message)

    async def start(self) -> None:
        if self._running:
            logger.warning("Server already running")
            return

        host = self.config.server.host
        port = self.config.server.port

        logger.info(f"Starting telnet server on {host}:{port}")

        loop = asyncio.get_event_loop()
        self._server = await telnetlib3.create_server(
            host=host,
            port=port,
            shell=self.shell,
            connect_maxwait=3.0,
            timeout=self.config.server.connection_timeout,
            encoding='latin-1',  # Byte-transparent transport layer
            encoding_errors='replace',
            force_binary=True,
        )

        self._running = True
        logger.info(f"Telnet server listening on {host}:{port}")

    async def stop(self) -> None:
        if not self._running:
            return

        logger.info("Stopping telnet server...")
        self._running = False

        for session in list(self.sessions.values()):
            await session.disconnect()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("Telnet server stopped")

    async def run(self) -> None:
        await self.start()
        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()


async def main():
    from .utils.logger import setup_logging
    setup_logging()

    server = TelnetServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())