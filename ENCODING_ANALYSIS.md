# Telnet Encoding Architecture Analysis

## The Core Problem

The fundamental issue is at `bbs/app/telnet_server.py:121`:

```python
self._server = await telnetlib3.create_server(
    ...
    encoding='utf-8',           # ← This is the bottleneck
    encoding_errors='replace',  # ← Corruption happens here
    ...
)
```

**Current data flow:**
```
Client CP866 bytes → telnetlib3 UTF-8 decode → CORRUPTED → Session → App
         ↓
    0x8F 0xE0 0xA8...  →  "������" (U+FFFD replacement chars)
```

The corruption is **irreversible** because by the time `Session.read()` gets the data, the original bytes are gone.

---

## Impact

- **Output** can look correct after encoding selection (session encodes properly)
- **Input** from legacy clients is corrupted before the app sees it
- Users sending CP437/CP866/KOI8 text get replacement characters
- Problem occurs even before user can select their encoding

---

## Option 1: Raw 8-bit Telnet + App-Level Decoding

Run telnetlib3 with `encoding=None` (raw bytes mode).

### Pros
- Complete control over encoding
- No data corruption possible
- Most correct solution

### Cons
- telnetlib3's `TelnetReader.read()` returns `bytes` instead of `str`
- All Session I/O methods need refactoring
- More complex error handling

### Variant: Latin-1 Transport (Recommended)

Use `encoding='latin-1'` instead of raw mode. Latin-1 is **byte-transparent** (every value 0x00-0xFF maps 1:1 to a Unicode codepoint).

```
Client CP866 bytes → telnetlib3 latin-1 decode → "Ïàèâåâ" → Session re-decodes → "Привет"
       ↓
  0x8F 0xE0 0xA8... → preserved as single chars → re-encode latin-1 → decode CP866
```

**Advantages over raw mode:**
- telnetlib3 still works with strings (no API changes)
- Simpler code changes
- Same correctness guarantees

---

## Option 2: Encoding Switch After Login

Start in UTF-8, switch the telnet layer after user selects encoding.

### Pros
- Minimal initial changes
- UTF-8 clients work immediately

### Cons
- **Won't fully work**: telnetlib3's reader has already decoded incoming bytes
- Changing writer encoding only affects output
- Pre-selection input still vulnerable to corruption
- Cannot "un-corrupt" already-received data

### Verdict: Not viable

---

## Option 3: ASCII-Only Login, Then Raw Mode

Use strict ASCII for initial prompts, switch to raw 8-bit mode after encoding selection.

### Pros
- Minimizes corruption window
- Login prompts already mostly ASCII

### Cons
- "Switching modes" mid-session is awkward with telnetlib3
- Would need to close reader/writer, get raw socket, continue manually
- Significant plumbing required
- Complex state management

### Verdict: Over-engineered for the benefit

---

## Option 4: Segment Transport by Protocol

Keep telnet limited to UTF-8/ASCII, offer SSH for legacy encodings.

### Pros
- Already partially implemented (SSH uses `encoding=None`)
- Clean separation of concerns
- SSH has true binary transfer support
- Minimal code changes

### Cons
- Limits telnet functionality
- Legacy BBS users may expect telnet to work
- Documentation burden

### Current State

SSH gateway (`ssh_gateway.py:348`) already uses raw mode:
```python
await asyncssh.create_server(
    ...
    encoding=None  # Raw binary mode
)
```

The `SSHReaderWriter` class handles bytes directly, which is why SSH has full binary transfer support.

---

## Comparison Table

| Approach | Complexity | Correctness | Binary I/O | Notes |
|----------|------------|-------------|------------|-------|
| **Latin-1 transport** | Low | Full | Via existing raw methods | Best overall balance |
| Raw telnetlib3 | Medium | Full | Native | Good if latin-1 has edge cases |
| ASCII login → raw | High | Full | After switch | Over-engineered |
| Protocol segmentation | Low | Partial | SSH only | Document "use SSH for legacy" |

---

## Recommended: Latin-1 Transport Layer

### Why Latin-1?

1. **Byte-transparent**: Every byte 0x00-0xFF survives round-trip
2. **Minimal changes**: telnetlib3 API stays the same (strings)
3. **Universal**: Works for UTF-8, CP437, CP866, KOI8, all encodings
4. **Simple mental model**: Transport layer = bytes, App layer = encoding

### How It Works

**Key insight**: The intermediate latin-1 string is **not readable text**. It's a byte-preserving container. The characters look like garbage until the application layer re-decodes with the correct encoding.

| Step | UTF-8 Client | CP866 Client |
|------|--------------|--------------|
| Client sends | `0xD0 0x9F` (UTF-8 "П") | `0x8F` (CP866 "П") |
| telnetlib3 latin-1 decode | `"Ð\x9f"` (U+00D0, U+009F) | `"\x8f"` (U+008F, control char) |
| Intermediate readable? | No (garbage) | No (invisible control) |
| Bytes preserved? | ✓ (0xD0 0x9F intact) | ✓ (0x8F intact) |
| Session re-decode | UTF-8 → "П" | CP866 → "П" |

The latin-1 layer is purely mechanical byte preservation, not interpretation.

### Required Changes

#### 1. `bbs/app/telnet_server.py:121`

```python
# Change from:
encoding='utf-8',

# To:
encoding='latin-1',  # Byte-transparent transport
```

#### 2. `bbs/app/session.py` - Read Method

```python
async def read(self, size: int = 1) -> str:
    """Read and decode using session encoding."""
    if not self.reader:
        return ""
    # telnetlib3 gives us latin-1 encoded string (byte-transparent)
    raw = await self.reader.read(size)
    if not raw:
        return ""
    # Re-encode to bytes via latin-1, then decode with actual encoding
    raw_bytes = raw.encode('latin-1', errors='replace')
    return raw_bytes.decode(self.capabilities.encoding, errors='replace')
```

#### 3. `bbs/app/session.py` - Write Method

```python
async def write(self, data: bytes | str) -> None:
    """Encode using session encoding and write."""
    if isinstance(data, str):
        # Encode to bytes using session encoding
        data_bytes = data.encode(self.capabilities.encoding, errors='replace')
    else:
        data_bytes = data
    # Convert to latin-1 string for telnetlib3
    transport_str = data_bytes.decode('latin-1')
    if self.writer:
        self.writer.write(transport_str)
        await self.writer.drain()
```

**Important**: This `write()` method is for **text output only**. For binary transfers (XMODEM, ZMODEM, Kermit), callers must continue using `write_raw()` which handles IAC escaping and bypasses encoding entirely. The bytes parameter in `write()` assumes the bytes are already encoded in the session's target encoding—it's a convenience for pre-encoded text, not raw binary data.

#### 4. `bbs/app/session.py` - Readline Method

Update to use the new read() behavior, ensuring character-by-character reading works with the two-layer encoding.

### Estimated Effort

- `telnet_server.py`: 1 line
- `session.py`: ~50 lines modified
- Tests: Verify encoding round-trips work

---

## Alternative: Full Raw Mode

If latin-1 approach has edge cases, switch to `encoding=None`:

### Changes Required

```python
# telnet_server.py
encoding=None,  # Raw bytes

# session.py - all I/O methods change signature
async def read(self, size: int = 1) -> str:
    raw_bytes = await self.reader.read(size)  # Now returns bytes
    return raw_bytes.decode(self.capabilities.encoding, errors='replace')

async def write(self, data: bytes | str) -> None:
    if isinstance(data, str):
        data = data.encode(self.capabilities.encoding, errors='replace')
    self.writer.write(data)  # Now accepts bytes
```

More invasive but gives complete control.

---

## Decision Matrix

Choose based on priorities:

| Priority | Recommendation |
|----------|----------------|
| Minimize code changes | Protocol segmentation (document SSH for legacy) |
| Full legacy support with low risk | Latin-1 transport |
| Maximum control/correctness | Raw mode (encoding=None) |
| Quick fix, accept limitations | Keep current + document limitations |

---

## Implementation Status

**Implemented: Latin-1 Transport Layer** (2025-12)

### Changes Made

1. **`bbs/app/telnet_server.py`**
   - Changed `encoding='utf-8'` to `encoding='latin-1'` at line 121

2. **`bbs/app/session.py`**
   - `read()`: Now re-encodes latin-1 to bytes, then decodes with session encoding
   - `write()`: Now encodes with session encoding, then decodes as latin-1 for transport
   - `readline()`: Rewritten to work at byte level, buffers bytes and decodes at end
   - `_write_with_flow_control()`: Updated to use latin-1 transport
   - `read_raw()`: Updated docstring (latin-1 is now byte-transparent)
   - `set_encoding()`: Removed stale writer encoding updates
   - `__post_init__()`: Removed stale UTF-8 forcing
   - `negotiate()`: Removed stale UTF-8 forcing

### Behavior After Implementation

**Telnet sessions:**
- Transport layer uses latin-1 (byte-transparent, every byte 0x00-0xFF preserved)
- Session layer handles actual encoding (UTF-8, CP437, CP866, KOI8-R, etc.)
- Legacy clients sending CP437/CP866/KOI8 bytes are now correctly handled

**SSH sessions:**
- Transport uses UTF-8 natively (no latin-1 conversion)
- Reader returns Unicode strings, writer expects Unicode strings
- `read()`, `write()`, `readline()` all branch on `transport_type`

**Both transports:**
- Binary transfers via `read_raw()`/`write_raw()` work without corruption
