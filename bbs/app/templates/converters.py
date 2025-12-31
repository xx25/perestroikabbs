"""
Character set converters for templates
"""
import re


class CharsetConverter:
    """Convert UTF-8 templates to various character encodings"""

    # ASCII fallback for box drawing characters
    # Used for encodings that don't have native box drawing support
    BOX_TO_ASCII = {
        # Single line box
        '┌': '+', '┐': '+', '└': '+', '┘': '+',
        '─': '-', '│': '|', '├': '+', '┤': '+',
        '┬': '+', '┴': '+', '┼': '+',
        # Double line box
        '╔': '+', '╗': '+', '╚': '+', '╝': '+',
        '═': '=', '║': '|', '╠': '+', '╣': '+',
        '╦': '+', '╩': '+', '╬': '+',
        # Block elements
        '█': '#', '▄': '_', '▀': '^', '▌': '[',
        '▐': ']', '░': '.', '▒': ':', '▓': '#',
    }

    # Encodings where Python codec handles box drawing natively
    NATIVE_BOX_ENCODINGS = frozenset([
        'utf-8', 'cp437', 'cp850', 'cp852', 'cp855', 'cp866'
    ])

    # Encodings that need ASCII box char fallback (no box drawing in charset)
    ASCII_BOX_ENCODINGS = frozenset([
        'koi8-r', 'koi8-u', 'windows-1251', 'iso-8859-5',
        'x-mac-cyrillic', 'ascii', 'us-ascii'
    ])

    # ANSI escape sequence pattern
    ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[mGKHJl]')

    def convert(self, text: str, encoding: str, ansi_enabled: bool = True) -> bytes:
        """
        Convert UTF-8 text to target encoding

        Args:
            text: UTF-8 text to convert
            encoding: Target encoding (utf-8, cp437, ascii, etc.)
            ansi_enabled: Whether to preserve ANSI escape codes

        Returns:
            Converted text as bytes
        """
        # Strip ANSI codes if not supported
        if not ansi_enabled:
            text = self._strip_ansi(text)

        # Convert newlines to CRLF for telnet compatibility
        text = text.replace('\r\n', '\n').replace('\n', '\r\n')

        encoding_lower = encoding.lower()

        # Determine how to handle box drawing characters
        if self._has_native_box_drawing(encoding_lower):
            # Python codec handles box drawing natively - just encode
            pass
        elif self._needs_ascii_fallback(encoding_lower):
            # Replace box chars with ASCII equivalents
            text = self._replace_box_with_ascii(text)
        else:
            # Unknown encoding - try to preserve what we can
            text = self._convert_box_chars_safe(text, encoding)

        # Encode to target charset
        try:
            return text.encode(encoding, errors='replace')
        except LookupError:
            # Unknown encoding, fall back to UTF-8
            return text.encode('utf-8', errors='replace')

    def _has_native_box_drawing(self, encoding: str) -> bool:
        """Check if encoding has native box drawing support via Python codec."""
        if encoding in self.NATIVE_BOX_ENCODINGS:
            return True
        # Check for variants like 'cp866' in 'ibm866'
        for native in self.NATIVE_BOX_ENCODINGS:
            if native.replace('-', '') in encoding.replace('-', ''):
                return True
        return False

    def _needs_ascii_fallback(self, encoding: str) -> bool:
        """Check if encoding needs ASCII fallback for box drawing."""
        for enc in self.ASCII_BOX_ENCODINGS:
            if enc in encoding:
                return True
        return False

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape sequences from text."""
        return self.ANSI_PATTERN.sub('', text)

    def _replace_box_with_ascii(self, text: str) -> str:
        """Replace UTF-8 box drawing characters with ASCII equivalents."""
        for box_char, ascii_char in self.BOX_TO_ASCII.items():
            text = text.replace(box_char, ascii_char)
        return text

    def _convert_box_chars_safe(self, text: str, encoding: str) -> str:
        """
        Safely convert box chars for unknown encodings.

        Tries to encode each character, falls back to ASCII if it fails.
        """
        result = []
        for char in text:
            if char in self.BOX_TO_ASCII:
                try:
                    char.encode(encoding)
                    result.append(char)
                except UnicodeEncodeError:
                    result.append(self.BOX_TO_ASCII[char])
            else:
                result.append(char)
        return ''.join(result)
