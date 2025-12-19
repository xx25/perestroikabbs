"""
BBS Template System

Supports 4 display modes:
- 80x24 with ANSI
- 80x24 plain text
- 40x24 with ANSI
- 40x24 plain text
"""

from .engine import TemplateEngine, DisplayMode, DisplayConfig
from .converters import CharsetConverter
from .helpers import ANSIHelper, BoxDrawingHelper

__all__ = [
    'TemplateEngine',
    'DisplayMode',
    'DisplayConfig',
    'CharsetConverter',
    'ANSIHelper',
    'BoxDrawingHelper'
]