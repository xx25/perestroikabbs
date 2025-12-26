# Perestroika BBS

A modern Python BBS (Bulletin Board System) with support for legacy terminals, ANSI art, RIPscrip graphics, and classic file transfer protocols.

## Features

- **Multi-Transport**: Telnet, SSH, and STDIO (mgetty) support
- **Multi-Encoding**: UTF-8, CP437 (DOS), ISO-8859-*, KOI8-R, Windows-1251/1252, Shift_JIS
- **ANSI Art**: Full ANSI color support with automatic transcoding per-session
- **RIPscrip**: Auto-detection and support for RIPscrip-capable clients
- **Message Boards**: Public message boards with access controls
- **Private Mail**: User-to-user messaging with inbox/sent folders
- **Multi-User Chat**: Real-time chat rooms with whisper support
- **File Library**: Organized file areas with upload/download
- **File Transfers**: XMODEM (pure Python), ZMODEM and Kermit (via PTY)
- **User Management**: Registration, Argon2 authentication, access levels
- **Admin Tools**: User management, board admin, IP banning, statistics
- **Terminal Flexibility**: Works with any screen size (40x24 to custom)

## Quick Start

### With Docker (Recommended)

```bash
make build    # Build Docker images
make up       # Start BBS + MySQL
make migrate  # Initialize database

telnet localhost 2323
```

### Without Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Configure database in config.toml
python3 -m alembic upgrade head
python3 -m bbs.app.main
```

## Requirements

- Python 3.11+
- MySQL 5.7+ or MariaDB 10.2+
- For ZMODEM: `lrzsz` package
- For Kermit: `ckermit` package

## Tested Clients

| Type | Clients |
|------|---------|
| Modern | Windows Terminal, iTerm2, PuTTY, macOS Terminal |
| DOS | Telix, Telemate, ProComm Plus (via DOSBox) |
| BBS | SyncTERM, NetRunner, mTelnet |
| RIPscrip | RIPterm 1.54, RIPtel |

## Configuration

```toml
[server]
host = "0.0.0.0"
port = 2323
max_connections = 100

[db]
dsn = "mysql+aiomysql://user:pass@host:port/database"

[charset]
default_encoding = "utf-8"
supported_encodings = ["utf-8", "cp437", "iso-8859-1", ...]

[transfers]
rz_path = "/usr/bin/rz"
sz_path = "/usr/bin/sz"
download_root = "/var/lib/bbs/files"
```

## Make Commands

| Command | Description |
|---------|-------------|
| `make build` | Build Docker images |
| `make up` / `make down` | Start/stop containers |
| `make logs` | View BBS logs |
| `make shell` | Shell into container |
| `make migrate` | Run database migrations |
| `make test-simple` | Quick connectivity tests |
| `make test-full` | Full test suite |
| `make health` | Check BBS status |

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and patterns |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development setup and testing |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment |
| [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) | Feature status tracking |

## Project Structure

```
bbs/app/
├── main.py              # Entry point
├── telnet_server.py     # Telnet server
├── ssh_gateway.py       # SSH server
├── session.py           # Session management
├── encoding.py          # Charset handling
├── security/            # Auth, rate limiting
├── storage/             # Database layer
├── templates/           # Jinja2 templates
├── transfers/           # File protocols
├── ui/                  # UI modules
└── assets/              # ANSI/RIP art
```

## Implementation Status

| Component | Status |
|-----------|--------|
| Core BBS | Complete |
| Telnet/SSH | Complete |
| File Transfers | Complete |
| Message Boards | Complete |
| Private Mail | Complete |
| Chat | Complete |
| Admin Tools | Complete |
| RIPscrip | Partial (detection + serving) |

See [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for details.

## Future Plans

- Door game support (DOOR.SYS)
- FidoNet gateway
- Web interface
- REST API

See [docs/PLANS.md](docs/PLANS.md) for the full roadmap.

## License

MIT License
