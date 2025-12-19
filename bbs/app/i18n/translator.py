"""
Translator class for multi-language support in Perestroika BBS
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..utils.logger import get_logger

logger = get_logger("i18n.translator")


class Translator:
    """Handles language translations for the BBS"""

    def __init__(self, language: str = 'en', fallback_language: str = 'en'):
        self.current_language = language
        self.fallback_language = fallback_language
        self.translations: Dict[str, Dict] = {}
        self.languages_dir = Path(__file__).parent / 'languages'

        # Load the current and fallback languages
        self._load_language(fallback_language)
        if language != fallback_language:
            self._load_language(language)

    def _load_language(self, lang_code: str) -> bool:
        """Load a language file from JSON"""
        try:
            lang_file = self.languages_dir / f"{lang_code}.json"
            if lang_file.exists():
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                logger.info(f"Loaded language: {lang_code}")
                return True
            else:
                logger.warning(f"Language file not found: {lang_code}")
                return False
        except Exception as e:
            logger.error(f"Error loading language {lang_code}: {e}")
            return False

    def get(self, key: str, **kwargs) -> str:
        """
        Get a translated string by key

        Args:
            key: Dot-separated key path (e.g., 'login.username')
            **kwargs: Values for string interpolation

        Returns:
            Translated and formatted string
        """
        # Try current language first
        text = self._get_from_dict(self.translations.get(self.current_language, {}), key)

        # Fall back to default language if not found
        if text is None and self.current_language != self.fallback_language:
            text = self._get_from_dict(self.translations.get(self.fallback_language, {}), key)

        # If still not found, return the key itself
        if text is None:
            logger.debug(f"Translation not found for key: {key}")
            return f"[{key}]"

        # Handle string interpolation
        if kwargs:
            try:
                # Handle special pluralization case
                if 'count' in kwargs:
                    text = self._pluralize(text, kwargs['count'])

                # Format the string with provided values
                text = text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing interpolation value: {e} for key: {key}")
            except Exception as e:
                logger.error(f"Error formatting translation: {e}")

        return text

    def _get_from_dict(self, data: Dict, key: str) -> Optional[str]:
        """Navigate nested dictionary using dot notation"""
        keys = key.split('.')
        current = data

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None

        return current if isinstance(current, str) else None

    def _pluralize(self, text: str, count: int) -> str:
        """
        Handle pluralization for different languages

        For complex pluralization (like Russian), the JSON should contain:
        {
            "one": "1 сообщение",
            "few": "{count} сообщения",
            "many": "{count} сообщений"
        }
        """
        if isinstance(text, dict):
            # Russian pluralization rules
            if self.current_language == 'ru':
                if count % 10 == 1 and count % 100 != 11:
                    return text.get('one', str(count))
                elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
                    return text.get('few', text.get('other', str(count)))
                else:
                    return text.get('many', text.get('other', str(count)))
            # English and default pluralization
            else:
                if count == 1:
                    return text.get('one', str(count))
                else:
                    return text.get('other', str(count))

        # Simple string, just return it
        return text

    def set_language(self, lang_code: str) -> bool:
        """Change the current language"""
        if lang_code not in self.translations:
            if not self._load_language(lang_code):
                return False

        self.current_language = lang_code
        logger.info(f"Language changed to: {lang_code}")
        return True

    def get_available_languages(self) -> List[Dict[str, str]]:
        """Get list of available languages"""
        languages = []

        for lang_file in self.languages_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    languages.append({
                        'code': lang_code,
                        'name': data.get('_metadata', {}).get('name', lang_code),
                        'native_name': data.get('_metadata', {}).get('native_name', lang_code)
                    })
            except Exception as e:
                logger.error(f"Error reading language file {lang_file}: {e}")

        return languages

    def format_date(self, date: datetime, format: str = 'short') -> str:
        """Format a date according to the current language's locale"""
        if self.current_language == 'ru':
            if format == 'short':
                return date.strftime('%d.%m.%Y')  # DD.MM.YYYY
            elif format == 'long':
                # Russian month names
                months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                         'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
                return f"{date.day} {months[date.month-1]} {date.year}"
            elif format == 'time':
                return date.strftime('%H:%M')  # 24-hour format
            else:
                return date.strftime('%d.%m.%Y %H:%M')
        else:
            # English/default formatting
            if format == 'short':
                return date.strftime('%m/%d/%Y')  # MM/DD/YYYY
            elif format == 'long':
                return date.strftime('%B %d, %Y')
            elif format == 'time':
                return date.strftime('%I:%M %p')  # 12-hour format
            else:
                return date.strftime('%m/%d/%Y %I:%M %p')

    def format_number(self, number: float, decimals: int = 0) -> str:
        """Format a number according to the current language's locale"""
        if self.current_language == 'ru':
            # Russian uses space as thousands separator and comma for decimal
            if decimals > 0:
                formatted = f"{number:,.{decimals}f}"
                formatted = formatted.replace(',', ' ').replace('.', ',')
            else:
                formatted = f"{number:,.0f}".replace(',', ' ')
        else:
            # English/default formatting
            if decimals > 0:
                formatted = f"{number:,.{decimals}f}"
            else:
                formatted = f"{number:,.0f}"

        return formatted

    # Shortcut method for convenience
    def t(self, key: str, **kwargs) -> str:
        """Shortcut for get() method"""
        return self.get(key, **kwargs)