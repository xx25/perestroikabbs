"""
Template helpers for ANSI codes and box drawing
"""
from typing import Optional


class ANSIHelper:
    """ANSI escape sequence generator for templates"""

    @staticmethod
    def clear() -> str:
        """Clear screen and home cursor"""
        return "\x1b[2J\x1b[H"

    @staticmethod
    def home() -> str:
        """Move cursor to home position"""
        return "\x1b[H"

    @staticmethod
    def color(fg: Optional[int] = None, bg: Optional[int] = None,
              bold: bool = False, blink: bool = False,
              underline: bool = False, reverse: bool = False) -> str:
        """
        Generate ANSI color escape sequence

        Args:
            fg: Foreground color (0-7)
            bg: Background color (0-7)
            bold: Bold text
            blink: Blinking text
            underline: Underlined text
            reverse: Reverse video

        Returns:
            ANSI escape sequence
        """
        codes = []

        if bold:
            codes.append("1")
        if underline:
            codes.append("4")
        if blink:
            codes.append("5")
        if reverse:
            codes.append("7")
        if fg is not None and 0 <= fg <= 7:
            codes.append(str(30 + fg))
        if bg is not None and 0 <= bg <= 7:
            codes.append(str(40 + bg))

        if codes:
            return f"\x1b[{';'.join(codes)}m"
        return ""

    @staticmethod
    def reset() -> str:
        """Reset all attributes"""
        return "\x1b[0m"

    @staticmethod
    def goto(row: int, col: int) -> str:
        """Move cursor to specific position"""
        return f"\x1b[{row};{col}H"

    @staticmethod
    def up(n: int = 1) -> str:
        """Move cursor up n lines"""
        return f"\x1b[{n}A"

    @staticmethod
    def down(n: int = 1) -> str:
        """Move cursor down n lines"""
        return f"\x1b[{n}B"

    @staticmethod
    def forward(n: int = 1) -> str:
        """Move cursor forward n columns"""
        return f"\x1b[{n}C"

    @staticmethod
    def back(n: int = 1) -> str:
        """Move cursor back n columns"""
        return f"\x1b[{n}D"

    @staticmethod
    def save_cursor() -> str:
        """Save cursor position"""
        return "\x1b[s"

    @staticmethod
    def restore_cursor() -> str:
        """Restore cursor position"""
        return "\x1b[u"

    @staticmethod
    def hide_cursor() -> str:
        """Hide cursor"""
        return "\x1b[?25l"

    @staticmethod
    def show_cursor() -> str:
        """Show cursor"""
        return "\x1b[?25h"

    @staticmethod
    def clear_line() -> str:
        """Clear current line"""
        return "\x1b[2K"

    @staticmethod
    def clear_to_end() -> str:
        """Clear from cursor to end of line"""
        return "\x1b[K"


class BoxDrawingHelper:
    """Box drawing helper for templates"""

    STYLES = {
        'single': {
            'tl': '┌', 'tr': '┐', 'bl': '└', 'br': '┘',
            'h': '─', 'v': '│', 't': '┬', 'b': '┴',
            'l': '├', 'r': '┤', 'x': '┼'
        },
        'double': {
            'tl': '╔', 'tr': '╗', 'bl': '╚', 'br': '╝',
            'h': '═', 'v': '║', 't': '╦', 'b': '╩',
            'l': '╠', 'r': '╣', 'x': '╬'
        },
        'rounded': {
            'tl': '╭', 'tr': '╮', 'bl': '╰', 'br': '╯',
            'h': '─', 'v': '│', 't': '┬', 'b': '┴',
            'l': '├', 'r': '┤', 'x': '┼'
        },
        'ascii': {
            'tl': '+', 'tr': '+', 'bl': '+', 'br': '+',
            'h': '-', 'v': '|', 't': '+', 'b': '+',
            'l': '+', 'r': '+', 'x': '+'
        }
    }

    @classmethod
    def box(cls, width: int, height: int, style: str = 'single',
            title: Optional[str] = None, encoding: str = 'utf-8') -> str:
        """
        Generate a box with specified dimensions

        Args:
            width: Box width
            height: Box height
            style: Box style ('single', 'double', 'rounded', 'ascii')
            title: Optional title for box
            encoding: Target encoding

        Returns:
            Box as string
        """
        # Select appropriate style based on encoding
        if encoding in ['ascii', 'us-ascii']:
            style = 'ascii'
        elif style not in cls.STYLES:
            style = 'single'

        chars = cls.STYLES[style]
        lines = []

        # Top line
        top_line = chars['tl'] + chars['h'] * (width - 2) + chars['tr']
        if title and len(title) < width - 4:
            # Insert title in top line
            padding = (width - 2 - len(title)) // 2
            top_line = (chars['tl'] + chars['h'] * (padding - 1) +
                       ' ' + title + ' ' +
                       chars['h'] * (width - padding - len(title) - 3) +
                       chars['tr'])
        lines.append(top_line)

        # Middle lines
        for _ in range(height - 2):
            lines.append(chars['v'] + ' ' * (width - 2) + chars['v'])

        # Bottom line
        lines.append(chars['bl'] + chars['h'] * (width - 2) + chars['br'])

        return '\n'.join(lines)

    @classmethod
    def h_line(cls, width: int, style: str = 'single', encoding: str = 'utf-8') -> str:
        """
        Generate a horizontal line

        Args:
            width: Line width
            style: Line style
            encoding: Target encoding

        Returns:
            Horizontal line
        """
        if encoding in ['ascii', 'us-ascii']:
            return '-' * width

        chars = cls.STYLES.get(style, cls.STYLES['single'])
        return chars['h'] * width

    @classmethod
    def get_char(cls, char_type: str, style: str = 'single', encoding: str = 'utf-8') -> str:
        """
        Get a specific box drawing character

        Args:
            char_type: Character type (tl, tr, bl, br, h, v, etc.)
            style: Box style
            encoding: Target encoding

        Returns:
            Box drawing character
        """
        if encoding in ['ascii', 'us-ascii']:
            style = 'ascii'

        chars = cls.STYLES.get(style, cls.STYLES['single'])
        return chars.get(char_type, '+')