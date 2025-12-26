"""
Centralized display mode configuration.

This is the single source of truth for display mode determination,
replacing duplicated logic across session.py, templates/engine.py,
and ui/login.py.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class DisplayMode(Enum):
    """Four supported display modes based on terminal size and ANSI support."""

    STANDARD_ANSI = "80x24_ansi"  # 80x24 with ANSI colors
    STANDARD_PLAIN = "80x24_plain"  # 80x24 without ANSI
    NARROW_ANSI = "40x24_ansi"  # 40x24 with ANSI (for narrow terminals)
    NARROW_PLAIN = "40x24_plain"  # 40x24 without ANSI


@dataclass
class DisplayConfig:
    """
    Display configuration for a session.

    Attributes:
        width: Terminal width in columns
        height: Terminal height in rows
        ansi: Whether ANSI escape codes are supported
        mode: The computed display mode
    """

    width: int
    height: int
    ansi: bool
    mode: DisplayMode

    @classmethod
    def from_capabilities(
        cls, cols: int, rows: int, ansi: bool
    ) -> "DisplayConfig":
        """
        Create display config from terminal capabilities.

        This is the single source of truth for display mode determination.

        Args:
            cols: Terminal width in columns
            rows: Terminal height in rows
            ansi: Whether ANSI is supported

        Returns:
            DisplayConfig with computed mode
        """
        if cols <= 40:
            mode = DisplayMode.NARROW_ANSI if ansi else DisplayMode.NARROW_PLAIN
        else:
            mode = DisplayMode.STANDARD_ANSI if ansi else DisplayMode.STANDARD_PLAIN

        return cls(width=cols, height=rows, ansi=ansi, mode=mode)

    @classmethod
    def from_session(cls, session) -> "DisplayConfig":
        """
        Create display config from a session object.

        Args:
            session: Session with capabilities attribute

        Returns:
            DisplayConfig with computed mode
        """
        return cls.from_capabilities(
            cols=session.capabilities.cols,
            rows=session.capabilities.rows,
            ansi=session.capabilities.ansi,
        )


# Preset configurations for user selection during login
DISPLAY_PRESETS = {
    "1": (80, 24, True, "80x24 with ANSI colors (Recommended)"),
    "2": (80, 24, False, "80x24 plain text (No colors)"),
    "3": (40, 24, True, "40x24 with ANSI colors (Narrow)"),
    "4": (40, 24, False, "40x24 plain text (Narrow, no colors)"),
}


def get_display_config(choice: str) -> Tuple[int, int, bool]:
    """
    Get display configuration from preset choice.

    Args:
        choice: Preset key ('1', '2', '3', or '4')

    Returns:
        Tuple of (cols, rows, ansi) configuration
    """
    preset = DISPLAY_PRESETS.get(choice, DISPLAY_PRESETS["1"])
    return preset[0], preset[1], preset[2]


def compute_display_mode(cols: int, ansi: bool) -> DisplayMode:
    """
    Compute display mode from terminal parameters.

    This is a convenience function for cases where only the mode
    is needed without a full DisplayConfig.

    Args:
        cols: Terminal width in columns
        ansi: Whether ANSI is supported

    Returns:
        The appropriate DisplayMode
    """
    if cols <= 40:
        return DisplayMode.NARROW_ANSI if ansi else DisplayMode.NARROW_PLAIN
    return DisplayMode.STANDARD_ANSI if ansi else DisplayMode.STANDARD_PLAIN
