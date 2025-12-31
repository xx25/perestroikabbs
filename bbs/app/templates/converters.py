"""
Character set converters for templates
"""
import re
from typing import Dict, Tuple


class CharsetConverter:
    """Convert UTF-8 templates to various character encodings"""

    # Box drawing character mappings
    BOX_CHARS = {
        'utf-8': {
            # Single line box
            '┌': '┌', '┐': '┐', '└': '└', '┘': '┘',
            '─': '─', '│': '│', '├': '├', '┤': '┤',
            '┬': '┬', '┴': '┴', '┼': '┼',
            # Double line box
            '╔': '╔', '╗': '╗', '╚': '╚', '╝': '╝',
            '═': '═', '║': '║', '╠': '╠', '╣': '╣',
            '╦': '╦', '╩': '╩', '╬': '╬',
            # Block elements
            '█': '█', '▄': '▄', '▀': '▀', '▌': '▌',
            '▐': '▐', '░': '░', '▒': '▒', '▓': '▓',
        },
        'cp437': {
            # Single line box - CP437 codes
            '┌': '\xDA', '┐': '\xBF', '└': '\xC0', '┘': '\xD9',
            '─': '\xC4', '│': '\xB3', '├': '\xC3', '┤': '\xB4',
            '┬': '\xC2', '┴': '\xC1', '┼': '\xC5',
            # Double line box - CP437 codes
            '╔': '\xC9', '╗': '\xBB', '╚': '\xC8', '╝': '\xBC',
            '═': '\xCD', '║': '\xBA', '╠': '\xCC', '╣': '\xB9',
            '╦': '\xCB', '╩': '\xCA', '╬': '\xCE',
            # Block elements - CP437 codes
            '█': '\xDB', '▄': '\xDC', '▀': '\xDF', '▌': '\xDD',
            '▐': '\xDE', '░': '\xB0', '▒': '\xB1', '▓': '\xB2',
        },
        'cp866': {
            # Single line box - CP866 codes (same as CP437 for box drawing)
            '┌': '\xDA', '┐': '\xBF', '└': '\xC0', '┘': '\xD9',
            '─': '\xC4', '│': '\xB3', '├': '\xC3', '┤': '\xB4',
            '┬': '\xC2', '┴': '\xC1', '┼': '\xC5',
            # Double line box - CP866 codes
            '╔': '\xC9', '╗': '\xBB', '╚': '\xC8', '╝': '\xBC',
            '═': '\xCD', '║': '\xBA', '╠': '\xCC', '╣': '\xB9',
            '╦': '\xCB', '╩': '\xCA', '╬': '\xCE',
            # Block elements - CP866 codes
            '█': '\xDB', '▄': '\xDC', '▀': '\xDF', '▌': '\xDD',
            '▐': '\xDE', '░': '\xB0', '▒': '\xB1', '▓': '\xB2',
        },
        'x-mac-cyrillic': {
            # MacCyrillic doesn't have box drawing, use ASCII fallback
            '┌': '+', '┐': '+', '└': '+', '┘': '+',
            '─': '-', '│': '|', '├': '+', '┤': '+',
            '┬': '+', '┴': '+', '┼': '+',
            # Double line box - ASCII fallback
            '╔': '*', '╗': '*', '╚': '*', '╝': '*',
            '═': '=', '║': '|', '╠': '*', '╣': '*',
            '╦': '*', '╩': '*', '╬': '*',
            # Block elements - ASCII fallback
            '█': '#', '▄': '_', '▀': '^', '▌': '[',
            '▐': ']', '░': '.', '▒': '::', '▓': '##',
        },
        'ascii': {
            # Single line box - ASCII fallback
            '┌': '+', '┐': '+', '└': '+', '┘': '+',
            '─': '-', '│': '|', '├': '+', '┤': '+',
            '┬': '+', '┴': '+', '┼': '+',
            # Double line box - ASCII fallback
            '╔': '#', '╗': '#', '╚': '#', '╝': '#',
            '═': '=', '║': '#', '╠': '#', '╣': '#',
            '╦': '#', '╩': '#', '╬': '#',
            # Block elements - ASCII fallback
            '█': '#', '▄': '_', '▀': '^', '▌': '[',
            '▐': ']', '░': '.', '▒': 'o', '▓': 'O',
        }
    }

    # Encodings that need ASCII box char fallback (no box drawing in charset)
    ASCII_BOX_ENCODINGS = [
        'koi8-r', 'koi8-u', 'windows-1251', 'iso-8859-5',
        'x-mac-cyrillic', 'ascii', 'us-ascii'
    ]

    # ANSI escape sequence pattern
    ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[mGKHJl]')

    def __init__(self):
        """Initialize charset converter"""
        pass

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

        # Convert box drawing characters based on encoding
        if encoding_lower == 'utf-8':
            # UTF-8 can handle everything
            pass
        elif encoding_lower == 'cp437' or '437' in encoding_lower:
            text = self._convert_box_chars(text, 'cp437')
        elif encoding_lower == 'cp866' or '866' in encoding_lower:
            text = self._convert_box_chars(text, 'cp866')
        elif any(enc in encoding_lower for enc in self.ASCII_BOX_ENCODINGS):
            # These encodings don't have box drawing chars, use ASCII
            text = self._convert_box_chars(text, 'ascii')
        else:
            # For other encodings, try to preserve what we can
            text = self._convert_box_chars_safe(text, encoding)

        # Encode to target charset
        try:
            return text.encode(encoding, errors='replace')
        except LookupError:
            # Unknown encoding, fall back to UTF-8
            return text.encode('utf-8', errors='replace')

    def _strip_ansi(self, text: str) -> str:
        """
        Remove ANSI escape sequences from text

        Args:
            text: Text with ANSI codes

        Returns:
            Text without ANSI codes
        """
        return self.ANSI_PATTERN.sub('', text)

    def _convert_box_chars(self, text: str, target: str) -> str:
        """
        Convert UTF-8 box drawing characters to target charset

        Args:
            text: Text with UTF-8 box chars
            target: Target charset ('cp437' or 'ascii')

        Returns:
            Text with converted box chars
        """
        if target not in self.BOX_CHARS:
            return text

        mappings = self.BOX_CHARS[target]
        for utf8_char, replacement in mappings.items():
            text = text.replace(utf8_char, replacement)

        return text

    def _convert_box_chars_safe(self, text: str, encoding: str) -> str:
        """
        Safely convert box chars for unknown encodings

        Args:
            text: Text with UTF-8 box chars
            encoding: Target encoding

        Returns:
            Text with safely converted chars
        """
        # Try to encode each box char, fall back to ASCII if it fails
        result = []
        for char in text:
            if char in self.BOX_CHARS['utf-8']:
                try:
                    # Try to encode the character
                    char.encode(encoding)
                    result.append(char)
                except UnicodeEncodeError:
                    # Fall back to ASCII equivalent
                    ascii_char = self.BOX_CHARS['ascii'].get(char, '+')
                    result.append(ascii_char)
            else:
                result.append(char)

        return ''.join(result)

    def _supports_extended_ascii(self, encoding: str) -> bool:
        """
        Check if encoding supports extended ASCII characters

        Args:
            encoding: Encoding name

        Returns:
            True if encoding supports extended ASCII
        """
        # Encodings that support extended ASCII/box drawing
        extended_encodings = [
            'cp437', 'cp850', 'cp852', 'cp855', 'cp866',
            'iso-8859-1', 'iso-8859-2', 'iso-8859-5',
            'windows-1250', 'windows-1251', 'windows-1252',
            'koi8-r', 'koi8-u'
        ]

        encoding_lower = encoding.lower()
        return any(enc in encoding_lower for enc in extended_encodings)