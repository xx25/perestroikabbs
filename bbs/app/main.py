#!/usr/bin/env python3

import asyncio
import signal
import sys
from pathlib import Path

from .storage.db import close_database, create_tables, init_database
from .telnet_server import TelnetServer
from .utils.config import load_config
from .utils.logger import setup_logging

logger = setup_logging()


async def setup_database() -> None:
    logger.info("Initializing database...")
    await init_database()

    try:
        await create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


async def shutdown(server: TelnetServer) -> None:
    logger.info("Shutting down BBS...")
    await server.stop()
    await close_database()
    logger.info("Shutdown complete")


async def main_async() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.toml"

    if not Path(config_path).exists() and Path("config.example.toml").exists():
        logger.warning(f"Config file '{config_path}' not found. Using example config.")
        config_path = "config.example.toml"

    config = load_config(config_path)
    logger.info(f"Configuration loaded from {config_path}")

    await setup_database()

    server = TelnetServer()

    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        # Set event to trigger graceful shutdown in the main loop
        # Don't call sys.exit() here - let the async shutdown complete first
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting Perestroika BBS...")
        logger.info(f"Telnet server: {config.server.host}:{config.server.port}")

        # Start the server
        await server.start()

        # Wait for shutdown signal
        await shutdown_event.wait()
        logger.info("Shutdown signal received, cleaning up...")

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        await shutdown(server)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()