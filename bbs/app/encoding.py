import codecs
from typing import Dict, List, Optional, Tuple

try:
    import cchardet as chardet
except ImportError:
    import chardet


class CodecIO:
    def __init__(self, encoding: str = "utf-8"):
        self.encoding = self._validate_encoding(encoding)
        self._encoder = codecs.getencoder(self.encoding)
        self._decoder = codecs.getdecoder(self.encoding)

    @staticmethod
    def _validate_encoding(encoding: str) -> str:
        try:
            codecs.lookup(encoding)
            return encoding
        except LookupError:
            return "utf-8"

    def encode(self, text: str) -> bytes:
        try:
            return text.encode(self.encoding, errors="replace")
        except (UnicodeEncodeError, AttributeError):
            return text.encode("utf-8", errors="replace")

    def decode(self, data: bytes) -> str:
        try:
            return data.decode(self.encoding, errors="replace")
        except (UnicodeDecodeError, AttributeError):
            return data.decode("utf-8", errors="replace")


class CharsetManager:
    COMMON_ENCODINGS = [
        ("UTF-8", "utf-8"),
        ("CP437 (DOS)", "cp437"),
        ("ISO-8859-1 (Latin-1)", "iso-8859-1"),
        ("ISO-8859-2 (Central European)", "iso-8859-2"),
        ("ISO-8859-5 (Cyrillic)", "iso-8859-5"),
        ("ISO-8859-7 (Greek)", "iso-8859-7"),
        ("KOI8-R (Russian)", "koi8-r"),
        ("Windows-1251 (Cyrillic)", "windows-1251"),
        ("Windows-1252 (Western)", "windows-1252"),
        ("MacRoman", "macintosh"),
        ("Shift_JIS (Japanese)", "shift_jis"),
    ]

    CP437_MAPPING = {
        0x00: " ", 0x01: "☺", 0x02: "☻", 0x03: "♥", 0x04: "♦",
        0x05: "♣", 0x06: "♠", 0x07: "•", 0x08: "◘", 0x09: "○",
        0x0A: "◙", 0x0B: "♂", 0x0C: "♀", 0x0D: "♪", 0x0E: "♫",
        0x0F: "☼", 0x10: "►", 0x11: "◄", 0x12: "↕", 0x13: "‼",
        0x14: "¶", 0x15: "§", 0x16: "▬", 0x17: "↨", 0x18: "↑",
        0x19: "↓", 0x1A: "→", 0x1B: "←", 0x1C: "∟", 0x1D: "↔",
        0x1E: "▲", 0x1F: "▼",
    }

    def __init__(self, supported_encodings: Optional[List[str]] = None):
        self.supported_encodings = supported_encodings or [
            enc[1] for enc in self.COMMON_ENCODINGS
        ]

    def detect_encoding(self, data: bytes) -> str:
        if not data:
            return "utf-8"

        try:
            result = chardet.detect(data)
            if result and result["encoding"]:
                encoding = result["encoding"].lower()
                if encoding in self.supported_encodings:
                    return encoding
        except Exception:
            pass

        for encoding in ["utf-8", "cp437", "iso-8859-1"]:
            try:
                data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue

        return "utf-8"

    def get_encoding_menu(self) -> List[Tuple[str, str]]:
        menu = []
        for display, encoding in self.COMMON_ENCODINGS:
            if encoding in self.supported_encodings:
                menu.append((display, encoding))
        return menu

    def transcode(self, text: str, from_enc: str, to_enc: str) -> bytes:
        try:
            if from_enc == to_enc:
                return text.encode(to_enc, errors="replace")

            decoded = text if isinstance(text, str) else text.decode(from_enc, errors="replace")
            return decoded.encode(to_enc, errors="replace")
        except Exception:
            return text.encode("utf-8", errors="replace") if isinstance(text, str) else text

    def map_cp437_to_unicode(self, byte: int) -> str:
        return self.CP437_MAPPING.get(byte, chr(byte) if byte < 128 else "?")

    def prepare_ansi_art(self, art: str, target_encoding: str) -> bytes:
        if target_encoding == "cp437":
            return art.encode("cp437", errors="replace")
        elif target_encoding == "utf-8":
            return art.encode("utf-8")
        else:
            result = []
            for char in art:
                try:
                    char.encode(target_encoding)
                    result.append(char)
                except UnicodeEncodeError:
                    if ord(char) in self.CP437_MAPPING.values():
                        result.append(" ")
                    else:
                        result.append("?")
            return "".join(result).encode(target_encoding, errors="replace")