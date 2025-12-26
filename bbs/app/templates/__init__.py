"""
BBS Template System

Supports 4 display modes:
- 80x24 with ANSI
- 80x24 plain text
- 40x24 with ANSI
- 40x24 plain text
"""

from .engine import TemplateEngine
from .converters import CharsetConverter
from .helpers import ANSIHelper, BoxDrawingHelper

# Re-export from centralized display module for backward compatibility
from ..display import DisplayMode, DisplayConfig

__all__ = [
    'TemplateEngine',
    'DisplayMode',
    'DisplayConfig',
    'CharsetConverter',
    'ANSIHelper',
    'BoxDrawingHelper'
]