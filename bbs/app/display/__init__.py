"""
Display configuration package.

Centralizes display mode logic that was previously duplicated across:
- session.py (update_display_mode)
- templates/engine.py (DisplayConfig.from_session)
- ui/login.py (select_display_mode)
"""

from .mode import DisplayMode, DisplayConfig, DISPLAY_PRESETS, get_display_config

__all__ = [
    'DisplayMode',
    'DisplayConfig',
    'DISPLAY_PRESETS',
    'get_display_config',
]
