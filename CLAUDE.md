# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Development with Docker (recommended)
make build              # Build Docker images
make up                 # Start BBS + MySQL containers
make down               # Stop containers
make logs               # View BBS logs
make shell              # Shell into BBS container
make migrate            # Run Alembic migrations

# Local development
pip install -e ".[dev]"
python3 -m bbs.app.main [config.toml]

# Testing
make test-simple        # Quick connectivity tests (8 tests)
make test-full          # Full test suite via Docker
make test-perf          # 100 concurrent connections stress test
make health             # Check if BBS responds on port 2323

# Code quality
black bbs/              # Format code
ruff check bbs/         # Lint
mypy bbs/               # Type checking
```

## Architecture Overview

**Entry flow:** `main.py` → `TelnetServer` → `Session` → `LoginUI` → `MainMenu` → UI modules

### Key Components

- **TelnetServer** (`telnet_server.py`): Async telnet using `telnetlib3` with latin-1 transport layer for byte-transparency
- **Session** (`session.py`): Per-connection state including user, encoding, capabilities, transport type (TELNET/SSH)
- **Encoding** (`encoding.py`): `CharsetManager` handles 13+ encodings; `CodecIO` per-session codec
- **Storage** (`storage/`): SQLAlchemy 2.0 async with Repository pattern (`UserRepository`, `PostRepository`, etc.)
- **UI Modules** (`ui/`): `LoginUI`, `MainMenu`, `BoardsUI`, `MailUI`, `ChatUI`, `FileBrowserUI`, `AdminUI`
- **Transfers** (`transfers/`): Pure Python XMODEM; PTY-wrapped ZMODEM (`lrzsz`) and Kermit

### Transport Types

Two transport modes in `SessionTransport` enum:
- **TELNET**: Requires IAC (0xFF) byte escaping for binary data
- **SSH**: Raw binary, no escaping

Binary I/O uses `Session.write_raw()` / `Session.read_raw()` which handle escaping based on transport type.

### Display Mode System

Four display modes based on terminal capabilities:
- 80x24 ANSI (default), 80x24 Plain, 40x24 ANSI, 40x24 Plain

Each mode has separate Jinja2 templates in `templates/templates/`. Mode selected via `Session.display_mode`.

### Encoding Architecture

- Internal: UTF-8 throughout
- Transport layer: latin-1 (byte-transparent for telnetlib3)
- Application layer: Per-session encoding via `Session.codec`
- Charset negotiation happens during login

## Key Patterns

1. **All I/O is async** - Never use blocking calls in the event loop
2. **Use `Session.codec`** for all text encoding/decoding
3. **Use Repository pattern** for database access (not raw SQL)
4. **Check `access_level`** before exposing features
5. **Use `Session.write()`** for text, `Session.write_raw()` for binary
6. **Template rendering** via `Session.render_template()` respects display mode

## Configuration

TOML-based config with Pydantic validation. Key sections:
- `[server]` - host, port, max_connections
- `[db]` - MySQL DSN with aiomysql
- `[charset]` - default_encoding, supported_encodings list
- `[transfers]` - paths to rz/sz/kermit binaries
- `[security]` - Argon2 params, rate limiting

Access via `get_config()` singleton.

## Database

MySQL/MariaDB with async SQLAlchemy. Models in `storage/models.py`:
- User, Session, Board, Post, PrivateMessage, ChatRoom, ChatMessage, File, FileArea

Migrations via Alembic: `python3 -m alembic upgrade head`

## Default Ports

- Telnet: 2323
- MySQL (Docker): 3307 (maps to container's 3306)
