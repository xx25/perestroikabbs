"""
Template engine for BBS screens
"""
import os
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

from .converters import CharsetConverter
from .helpers import ANSIHelper, BoxDrawingHelper
from ..utils.logger import get_logger

logger = get_logger("templates.engine")


class DisplayMode(Enum):
    """Four supported display modes"""
    STANDARD_ANSI = "80x24_ansi"    # 80x24 with ANSI
    STANDARD_PLAIN = "80x24_plain"   # 80x24 without ANSI
    NARROW_ANSI = "40x24_ansi"       # 40x24 with ANSI
    NARROW_PLAIN = "40x24_plain"     # 40x24 without ANSI


@dataclass
class DisplayConfig:
    """Display configuration for a session"""
    width: int
    height: int
    ansi: bool
    mode: DisplayMode

    @classmethod
    def from_session(cls, session) -> 'DisplayConfig':
        """Create display config from session capabilities"""
        width = session.capabilities.cols
        height = session.capabilities.rows
        ansi = session.capabilities.ansi

        if width == 40:
            mode = DisplayMode.NARROW_ANSI if ansi else DisplayMode.NARROW_PLAIN
        else:
            mode = DisplayMode.STANDARD_ANSI if ansi else DisplayMode.STANDARD_PLAIN

        return cls(width=width, height=height, ansi=ansi, mode=mode)


class TemplateEngine:
    """
    Template engine that renders screens for different display modes
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize template engine

        Args:
            template_dir: Path to templates directory
        """
        if template_dir is None:
            # Default to templates directory relative to this file
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = Path(template_dir)
        self.charset_converter = CharsetConverter()

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Register helpers as globals
        self.env.globals['ansi'] = ANSIHelper()
        self.env.globals['box'] = BoxDrawingHelper()

        # Register filters
        self._register_filters()

        # Cache for compiled templates
        self.cache: Dict[str, Any] = {}

        logger.info(f"Template engine initialized with directory: {self.template_dir}")

    def _register_filters(self):
        """Register custom Jinja2 filters"""
        self.env.filters['center'] = lambda s, w: str(s).center(w)
        self.env.filters['ljust'] = lambda s, w, f=' ': str(s).ljust(w, f)
        self.env.filters['rjust'] = lambda s, w, f=' ': str(s).rjust(w, f)
        self.env.filters['indent'] = lambda s, w: '\n'.join(' ' * w + line for line in str(s).split('\n'))

    def get_template_path(self, template_name: str, display_mode: DisplayMode) -> str:
        """
        Build template path for given name and display mode

        Args:
            template_name: Name of template (e.g., "motd", "menus/main")
            display_mode: Display mode

        Returns:
            Template path relative to template directory
        """
        return f"{template_name}/{display_mode.value}.j2"

    async def render(
        self,
        template_name: str,
        context: Dict[str, Any],
        display_mode: DisplayMode,
        encoding: str = "utf-8",
        language: str = "en"
    ) -> bytes:
        """
        Render a template for specific display mode

        Args:
            template_name: Name of template
            context: Template context variables
            display_mode: Display mode
            encoding: Target character encoding
            language: Language code

        Returns:
            Rendered template as bytes in target encoding
        """
        template_path = self.get_template_path(template_name, display_mode)

        # Add display context
        context = context.copy()
        context.update({
            'ansi_enabled': 'ansi' in display_mode.value,
            'width': 40 if '40x24' in display_mode.value else 80,
            'height': 24,
            'display_mode': display_mode.value,
            'encoding': encoding,
            'language': language
        })

        # Try to get cached template
        cache_key = f"{template_path}:{language}"
        template = self.cache.get(cache_key)

        if not template:
            try:
                template = self.env.get_template(template_path)
                self.cache[cache_key] = template
            except TemplateNotFound:
                logger.warning(f"Template not found: {template_path}")
                # Try fallback to ANSI version and strip if needed
                if '_plain' in display_mode.value:
                    fallback_mode = display_mode.value.replace('_plain', '_ansi')
                    fallback_path = f"{template_name}/{fallback_mode}.j2"
                    try:
                        template = self.env.get_template(fallback_path)
                        self.cache[cache_key] = template
                        logger.info(f"Using fallback template: {fallback_path}")
                    except TemplateNotFound:
                        logger.error(f"Fallback template also not found: {fallback_path}")
                        # Return error message
                        error_msg = f"Template not found: {template_name}"
                        return error_msg.encode(encoding, errors='replace')
                else:
                    # Return error message
                    error_msg = f"Template not found: {template_name}"
                    return error_msg.encode(encoding, errors='replace')

        # Render template
        try:
            rendered = template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template {template_path}: {e}")
            error_msg = f"Error rendering template: {e}"
            return error_msg.encode(encoding, errors='replace')

        # Convert to target encoding
        ansi_enabled = 'ansi' in display_mode.value
        return self.charset_converter.convert(rendered, encoding, ansi_enabled)

    def template_exists(self, template_name: str, display_mode: DisplayMode) -> bool:
        """
        Check if a template exists

        Args:
            template_name: Name of template
            display_mode: Display mode

        Returns:
            True if template exists
        """
        template_path = self.get_template_path(template_name, display_mode)
        full_path = self.template_dir / template_path
        return full_path.exists()