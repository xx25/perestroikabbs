# Perestroika BBS

A modern Python BBS (Bulletin Board System) with support for legacy terminals, ANSI art, RIPscrip graphics, and classic file transfer protocols.

## Features

- **Telnet Server**: Full async telnet implementation with NAWS, binary mode, and echo negotiation
- **Multi-Encoding Support**: UTF-8, CP437 (DOS), ISO-8859-*, KOI8-R, Windows-1251/1252, Shift_JIS, and more
- **ANSI Art**: Full support for ANSI colors and ASCII art with automatic transcoding
- **RIPscrip Graphics**: Auto-detection and support for RIPscrip-capable clients
- **Message Boards**: Hierarchical boards with threading support
- **Private Mail**: User-to-user messaging system
- **Multi-User Chat**: Real-time chat rooms with whisper support
- **File Library**: Organized file areas with upload/download capabilities
- **File Transfers**: XMODEM, ZMODEM, and Kermit protocol support
- **User Management**: Registration, authentication with Argon2, access levels
- **Terminal Flexibility**: Works with any screen size (vintage-friendly)
- **MySQL Persistence**: All data stored in MySQL with async SQLAlchemy

## Requirements

- Python 3.11+
- MySQL 5.7+ or MariaDB 10.2+
- For ZMODEM: `lrzsz` package installed
- For Kermit: `ckermit` package installed

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/perestroikabbs.git
cd perestroikabbs
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
# or for development:
pip install -e ".[dev]"
```

4. Set up MySQL database:
```sql
CREATE DATABASE perestroika_bbs;
CREATE USER 'bbs_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON perestroika_bbs.* TO 'bbs_user'@'localhost';
FLUSH PRIVILEGES;
```

5. Configure the BBS:
```bash
cp config.example.toml config.toml
# Edit config.toml with your database credentials and preferences
```

6. Initialize the database:
```bash
python3 -m alembic upgrade head
```

## Running the BBS

```bash
# Using the installed command
bbs

# Or directly with Python
python3 -m bbs.app.main

# With custom config file
bbs custom_config.toml
```

The BBS will start on port 2323 by default. Connect using any telnet client:

```bash
telnet localhost 2323
```

## Supported Clients

Tested with:
- **Modern**: Windows Terminal, iTerm2, PuTTY, macOS Terminal
- **Classic DOS**: Telix, Telemate, ProComm Plus (via DOSBox)
- **Specialized BBS**: SyncTERM, NetRunner, mTelnet
- **RIPscrip**: RIPterm 1.54, RIPtel

## Directory Structure

```
perestroika-bbs/
├── bbs/
│   └── app/
│       ├── main.py           # Entry point
│       ├── telnet_server.py  # Telnet server implementation
│       ├── session.py        # Session management
│       ├── encoding.py       # Charset handling
│       ├── ui/              # User interface modules
│       │   ├── login.py    # Login/registration UI
│       │   ├── menu.py      # Menu system
│       │   ├── boards.py    # Message boards UI
│       │   ├── mail.py      # Private mail UI
│       │   ├── chat.py      # Chat room UI
│       │   └── file_browser.py # File area UI
│       ├── transfers/       # File transfer protocols
│       ├── storage/         # Database models and repositories
│       ├── security/        # Authentication and security
│       ├── assets/          # ANSI and RIP assets
│       └── utils/          # Configuration and logging
├── migrations/             # Alembic database migrations
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── config.example.toml    # Example configuration
└── pyproject.toml        # Project metadata and dependencies
```

## Configuration

Key configuration options in `config.toml`:

```toml
[server]
host = "0.0.0.0"
port = 2323
max_connections = 100

[db]
dsn = "mysql+aiomysql://user:pass@host:port/database"

[security]
argon2_time_cost = 3
argon2_memory_cost = 65536
min_password_length = 8

[charset]
default_encoding = "utf-8"
supported_encodings = ["utf-8", "cp437", "iso-8859-1", ...]

[transfers]
rz_path = "/usr/bin/rz"
sz_path = "/usr/bin/sz"
download_root = "/var/lib/bbs/files"
```

## Development

Run tests:
```bash
pytest
```

Format code:
```bash
black bbs/
ruff check bbs/
```

Type checking:
```bash
mypy bbs/
```

## Security Notes

- Passwords are hashed using Argon2id
- Login throttling and rate limiting
- Session timeouts
- Path traversal protection for file transfers
- Configurable access levels for all features

## Roadmap

- [ ] Complete XMODEM/ZMODEM/Kermit implementations
- [ ] Full RIPscrip command parser
- [ ] SSH gateway support
- [ ] Door game support
- [ ] FidoNet/NNTP gateway
- [ ] Web interface
- [ ] REST API

## Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Based on the classic BBS systems of the 1980s and 1990s, bringing retro computing into the modern era with Python's async capabilities.