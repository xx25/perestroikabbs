# Plan: Add stdio mode for mgetty direct launching

## Goal
Enable the BBS to be launched directly from mgetty's `login.config` instead of using `telnet -8` as a bridge.

## Current State
- BBS is network-only (telnet on port 2323, optional SSH on 2222)
- mgetty provides stdin/stdout connected to modem TTY
- Current workaround: `telnet -8 127.0.0.1 2323`

## Solution Overview
Add a **stdio transport mode** following the existing SSH gateway pattern (`SSHReaderWriter`).

---

## Files to Modify

### 1. `bbs/app/session.py`
- Add `STDIO = "stdio"` to `SessionTransport` enum (line 31-34)
- Update `write_raw()` (line 250): STDIO uses raw bytes like SSH (no IAC escaping)
- Update `negotiate()` (line 84): Skip telnet negotiation for STDIO

### 2. Create `bbs/app/stdio_transport.py` (new file)
Adapter class following `SSHReaderWriter` pattern:
```python
class StdioReaderWriter:
    # Wraps stdin/stdout as asyncio streams
    # Provides: read(), write(), drain(), read_raw(), close()
    # Uses latin-1 for byte-transparent transport
```

### 3. Create `bbs/app/stdio_main.py` (new file)
Entry point for mgetty:
```python
# python3 -m bbs.app.stdio_main
# - Captures mgetty env vars (CALLER_ID, CONNECT, DEVICE)
# - Creates StdioReaderWriter on stdin/stdout
# - Runs single Session with transport_type=STDIO
# - Handles SIGHUP/SIGTERM for modem hangup
```

---

## Implementation Details

### StdioReaderWriter (stdio_transport.py)
- Use `asyncio.StreamReader`/`StreamWriter` on fd 0 and fd 1
- Background read loop feeds data into char/raw buffers
- `read()` returns characters for text I/O
- `read_raw()` returns bytes for binary transfers (ZMODEM/Kermit)
- `write()` accepts str or bytes, encodes as latin-1
- `transport` property for `write_raw()` compatibility

### stdio_main.py entry point
- Load config, init database (same as main.py)
- Capture mgetty environment variables
- Signal handlers:
  - `SIGHUP` - modem hangup, graceful disconnect
  - `SIGTERM` - clean shutdown
- Call `session.detect_ripscrip()` after session creation (RIPscrip terminals exist on modems too)
- Run login UI and main menu (same flow as telnet)

### Session changes
```python
# session.py line 31-35
class SessionTransport(Enum):
    TELNET = "telnet"
    SSH = "ssh"
    STDIO = "stdio"  # Add this

# session.py write_raw() - update condition
if self.transport_type == SessionTransport.TELNET:
    data = data.replace(b'\xff', b'\xff\xff')
# STDIO and SSH pass through unchanged

# session.py negotiate() - add early return
if self.transport_type != SessionTransport.TELNET:
    self.state = SessionState.LOGIN
    return
```

---

## mgetty Environment Variables

mgetty sets these environment variables before exec() (from `cnd.c:324-337`, `mgetty.c:1171`):

| Variable | Description | Example |
|----------|-------------|---------|
| `CALLER_ID` | Phone number (if Caller ID available) | `"+1-555-1234"` |
| `CALLER_NAME` | Caller name (if Caller ID provides it) | `"JOHN DOE"` |
| `CALL_DATE` | Date of call | `"12/23"` |
| `CALL_TIME` | Time of call | `"14:35"` |
| `CALLED_ID` | Called number/MSN (ISDN) | `"5551000"` |
| `CONNECT` | Modem connect string | `"CONNECT 14400/V.32bis"` |
| `DEVICE` | TTY device name | `"ttyS0"` |
| `TERM` | Terminal type (if configured) | `"vt100"` |

### Handling in stdio_main.py

Create `MgettyInfo` dataclass to capture and expose these:

```python
@dataclass
class MgettyInfo:
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
```

### Usage in Session

Store in `session.data['mgetty']` for:
- **Logging**: Log caller ID on connect for audit trail
- **Display**: Show caller info on sysop screens, "who's online"
- **Connection speed**: Parse CONNECT string to display baud rate
- **remote_addr**: Use `caller_id` as the session's remote address identifier

---

## mgetty Configuration

Example `/etc/mgetty+sendfax/login.config`:
```
*    -    -    /usr/bin/python3 -m bbs.app.stdio_main
```

Or with explicit config:
```
*    -    -    env BBS_CONFIG=/etc/bbs/config.toml /usr/bin/python3 -m bbs.app.stdio_main
```

---

## Binary Transfers
The existing PTY-based ZMODEM/Kermit transfers will work unchanged:
- They create their own PTY and pump data via `write_raw()`/`read_raw()`
- STDIO mode provides raw binary I/O just like SSH
- No IAC escaping needed since there's no telnet protocol layer

---

## Testing Strategy
1. Pipe test: `echo -e "1\n1\n" | python3 -m bbs.app.stdio_main`
2. Pseudo-modem: `socat PTY,link=/tmp/modem PTY,link=/tmp/term`
3. Real mgetty test with modem or Hayes-compatible emulator
