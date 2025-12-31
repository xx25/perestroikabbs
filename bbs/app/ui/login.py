import asyncio
from typing import Optional
from pathlib import Path

from ..encoding import CharsetManager
from ..session import Session
from ..storage.repositories import UserRepository
from ..security.auth import AuthManager
from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger("ui.login")


class LoginUI:
    def __init__(self, session: Session, charset_manager: CharsetManager):
        self.session = session
        self.charset_manager = charset_manager
        self.auth_manager = AuthManager()
        self.user_repo = UserRepository()
        self.max_attempts = 3

    async def run(self) -> bool:
        # 0. Show ASCII-only welcome screen (works on ANY terminal)
        await self.show_welcome()

        # 1. Select charset FIRST - so we can display language names correctly
        await self.select_encoding()

        # 2. Select display mode (resolution + ANSI)
        await self.select_display_mode()

        # 3. Select language - now we can show it in proper charset
        await self.select_language()

        # 4. NOW show MOTD using templates
        await self.show_motd_template()

        await self.session.writeline()
        await self.session.writeline(self.session.t('login.title'))
        await self.session.writeline()

        options = [
            ("L", self.session.t('login.login_option')),
            ("N", self.session.t('login.register_option')),
            ("G", self.session.t('login.guest_option')),
            ("Q", self.session.t('login.quit_option')),
        ]

        choice = await self.session.menu_select(options, f"\r\n{self.session.t('login.your_choice')}: ")

        if choice == "L":
            return await self.login()
        elif choice == "N":
            return await self.register()
        elif choice == "G":
            return await self.guest_login()
        else:
            return False

    async def select_language(self) -> None:
        """Allow user to select interface language - now charset is known"""
        config = get_config()
        supported = config.language.supported_languages

        # Language metadata: code -> (english_name, native_name)
        LANGUAGE_META = {
            "en": ("English", "English"),
            "ru": ("Russian", "Русский"),
            "zh": ("Chinese", "中文"),
            "es": ("Spanish", "Español"),
            "fr": ("French", "Français"),
            "de": ("German", "Deutsch"),
            "pl": ("Polish", "Polski"),
            "uk": ("Ukrainian", "Українська"),
        }

        await self.session.writeline()

        # Check if we can display unicode characters
        can_show_unicode = self.session.capabilities.encoding in ['utf-8', 'windows-1251', 'koi8-r']

        if can_show_unicode:
            await self.session.writeline("Select your language / Выберите язык:")
        else:
            await self.session.writeline("Select your language:")

        await self.session.writeline()

        for i, lang_code in enumerate(supported, 1):
            eng_name, native_name = LANGUAGE_META.get(lang_code, (lang_code, lang_code))
            if can_show_unicode and native_name != eng_name:
                await self.session.writeline(f"  [{i}] {native_name} ({eng_name})")
            else:
                await self.session.writeline(f"  [{i}] {eng_name}")

        await self.session.writeline()

        choice = await self.session.readline(f"Choice [1-{len(supported)}]: ")

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(supported):
                self.session.set_language(supported[idx])
            else:
                self.session.set_language(config.language.default_language)
        except ValueError:
            self.session.set_language(config.language.default_language)

    async def select_encoding(self) -> None:
        # Use simple ASCII for charset selection since we don't know encoding yet
        logger.info(f"Starting charset selection for session {self.session.id}")

        config = get_config()
        preview_text = config.charset.charset_preview_text
        preview_translit = config.charset.charset_preview_translit

        await self.session.writeline("\r\nSelect charset (find the line with correct text):")
        await self.session.writeline()

        encodings = self.charset_manager.get_encoding_menu()

        for i, (display, encoding) in enumerate(encodings, 1):
            # Build line prefix
            prefix = f" [{i}] {display}: "
            await self.session.write(prefix)

            if encoding == "ascii":
                # Show transliteration for 7-bit ASCII
                await self.session.writeline(preview_translit)
            else:
                # Encode preview text in this encoding and send raw bytes
                try:
                    encoded_bytes = preview_text.encode(encoding, errors='replace')
                    # Send via latin-1 (byte-transparent transport)
                    await self.session.write(encoded_bytes.decode('latin-1'))
                    await self.session.writeline()
                except Exception:
                    await self.session.writeline("(encoding error)")

        await self.session.writeline()

        while True:
            choice = await self.session.readline(f"Choice [1-{len(encodings)}]: ")

            try:
                idx = int(choice)
                if 1 <= idx <= len(encodings):
                    encoding = encodings[idx - 1][1]
                    self.session.set_encoding(encoding)
                    # Special handling for ASCII mode
                    if encoding == "ascii":
                        self.session.capabilities.seven_bit = True
                        self.session.capabilities.ansi = False
                        self.session.capabilities.color = False
                    await self.session.writeline(f"Encoding set to {encodings[idx - 1][0]}")
                    break
                else:
                    await self.session.writeline(self.session.t('common.invalid_choice'))

            except ValueError:
                await self.session.writeline(self.session.t('common.invalid_input'))

    async def select_display_mode(self) -> None:
        """Allow user to select terminal display mode (size + ANSI support)"""
        await self.session.writeline()
        await self.session.writeline("Select your terminal configuration:")
        await self.session.writeline()
        await self.session.writeline("  [1] 80x24 with ANSI colors (Recommended)")
        await self.session.writeline("  [2] 80x24 plain text (No colors)")
        await self.session.writeline("  [3] 40x24 with ANSI colors (Narrow color)")
        await self.session.writeline("  [4] 40x24 plain text (Narrow, no colors)")
        await self.session.writeline()

        choice = await self.session.readline("Selection [1]: ")

        configs = {
            "1": (80, 24, True),   # Standard ANSI
            "2": (80, 24, False),  # Standard Plain
            "3": (40, 24, True),   # Narrow ANSI
            "4": (40, 24, False),  # Narrow Plain
        }

        cols, rows, ansi = configs.get(choice, configs["1"])

        self.session.capabilities.cols = cols
        self.session.capabilities.rows = rows
        self.session.capabilities.ansi = ansi
        self.session.capabilities.color = ansi

        # Update display mode
        self.session.update_display_mode()

        mode_descriptions = {
            "1": "80x24 with ANSI colors",
            "2": "80x24 plain text",
            "3": "40x24 with ANSI colors",
            "4": "40x24 plain text"
        }

        await self.session.writeline(f"\n{mode_descriptions.get(choice, mode_descriptions['1'])} selected")

    async def login(self) -> bool:
        for attempt in range(self.max_attempts):
            await self.session.writeline()
            username = await self.session.readline(f"{self.session.t('login.username_prompt')}: ")

            if not username:
                continue

            password = await self.session.read_password(f"{self.session.t('login.password_prompt')}: ")

            user = await self.user_repo.get_by_username(username)

            if user:
                valid, needs_rehash = await self.auth_manager.verify_password(
                    password, user.password_hash
                )
                if not valid:
                    await self.session.writeline(f"\r\n{self.session.t('login.invalid_credentials')}")
                    if attempt < self.max_attempts - 1:
                        await self.session.writeline(self.session.t('login.attempts_remaining', count=self.max_attempts - attempt - 1))
                    await asyncio.sleep(1)
                    continue

                # Rehash password if using outdated parameters
                if needs_rehash:
                    new_hash = await self.auth_manager.hash_password(password)
                    await self.user_repo.update_password(user.id, new_hash)
                    logger.info(f"Rehashed password for user {user.username}")

                self.session.user_id = user.id
                self.session.username = user.username
                self.session.access_level = user.access_level

                await self.user_repo.update_last_login(user.id)
                logger.info(f"User {username} logged in (Session: {self.session.id})")
                return True

            else:
                await self.session.writeline(f"\r\n{self.session.t('login.invalid_credentials')}")
                if attempt < self.max_attempts - 1:
                    await self.session.writeline(self.session.t('login.attempts_remaining', count=self.max_attempts - attempt - 1))
                await asyncio.sleep(1)

        await self.session.writeline(f"\r\n{self.session.t('login.max_attempts')}")
        return False

    async def register(self) -> bool:
        await self.session.writeline()
        await self.session.writeline(self.session.t('register.title'))
        await self.session.writeline()

        while True:
            username = await self.session.readline(f"{self.session.t('register.username_prompt')}: ")

            if len(username) < 3:
                await self.session.writeline(self.session.t('register.username_short'))
                continue

            if len(username) > 20:
                await self.session.writeline(self.session.t('register.username_long'))
                continue

            if await self.user_repo.get_by_username(username):
                await self.session.writeline(self.session.t('register.username_taken'))
                continue

            break

        while True:
            password = await self.session.read_password(f"{self.session.t('register.password_prompt')}: ")

            if len(password) < 8:
                await self.session.writeline(f"\r\n{self.session.t('register.password_short')}")
                continue

            confirm = await self.session.read_password(f"{self.session.t('register.password_confirm')}: ")

            if password != confirm:
                await self.session.writeline(f"\r\n{self.session.t('register.password_mismatch')}")
                continue

            break

        await self.session.writeline()
        email = await self.session.readline(f"{self.session.t('register.email_prompt')}: ")
        real_name = await self.session.readline(f"{self.session.t('register.realname_prompt')}: ")
        location = await self.session.readline(f"{self.session.t('register.location_prompt')}: ")

        password_hash = await self.auth_manager.hash_password(password)

        user = await self.user_repo.create(
            username=username,
            password_hash=password_hash,
            email=email or None,
            real_name=real_name or None,
            location=location or None,
        )

        if user:
            self.session.user_id = user.id
            self.session.username = user.username
            self.session.access_level = user.access_level

            await self.session.writeline()
            await self.session.writeline(self.session.t('register.success', username=username))
            logger.info(f"New user registered: {username} (Session: {self.session.id})")
            return True

        else:
            await self.session.writeline(f"\r\n{self.session.t('register.failed')}")
            return False

    async def guest_login(self) -> bool:
        self.session.username = "Guest"
        self.session.access_level = 0
        await self.session.writeline(f"\r\n{self.session.t('login.guest_login')}")
        logger.info(f"Guest login (Session: {self.session.id})")
        return True

    async def show_motd(self) -> None:
        """Display MOTD after charset, language, and terminal are configured"""
        await self.session.clear_screen()

        config = get_config()
        motd_file = config.server.motd_asset

        try:
            motd_path = Path(__file__).parent.parent / "assets" / motd_file

            if motd_path.exists():
                with open(motd_path, "rb") as f:
                    content = f.read()

                # Display based on configured encoding
                if self.session.capabilities.encoding == "cp437" or "437" in self.session.capabilities.encoding:
                    await self.session.write(content)
                else:
                    await self.session.write(content.decode("utf-8", errors="replace"))
            else:
                await self.show_default_motd()
        except Exception as e:
            logger.warning(f"Could not load MOTD: {e}")
            await self.show_default_motd()

        await self.session.writeline()

    async def show_motd_template(self) -> None:
        """Show MOTD using the template system"""
        # Clear screen before showing MOTD
        await self.session.clear_screen()

        # Get system stats for the template
        from ..storage.repositories import SystemRepository
        sys_repo = SystemRepository()
        stats = await sys_repo.get_stats()

        # Get mgetty connection info if available
        mgetty = self.session.data.get('mgetty')

        # Prepare context - only include non-empty mgetty values
        context = {
            'total_users': stats.get('total_users', 0),
            'online_now': stats.get('active_sessions', 0),
            'messages_today': stats.get('messages_today', 0),
            'files_shared': stats.get('total_files', 0),
            'system_news': await self._get_system_news(),
            # Connection info (only if not empty)
            'caller_id': (mgetty.caller_id if mgetty and mgetty.caller_id else ''),
            'caller_name': (mgetty.caller_name if mgetty and mgetty.caller_name else ''),
            'connect': (mgetty.connect if mgetty and mgetty.connect else ''),
            'device': (mgetty.device if mgetty and mgetty.device else ''),
            'remote_addr': self.session.remote_addr or '',
        }

        # Render MOTD template
        await self.session.render_template('motd', **context)

        # Wait for user to press a key
        await self.session.read(1)

    async def _get_system_news(self) -> str:
        """Get latest system news"""
        # TODO: Implement actual news retrieval from database
        return "Welcome to the new template-based BBS system!"

    async def show_default_motd(self) -> None:
        """Show default MOTD with proper charset support"""
        if self.session.capabilities.ansi:
            await self.session.set_color(fg=6, bold=True)

            # Use appropriate box characters based on encoding
            if self.session.capabilities.encoding in ["utf-8", "windows-1251"]:
                # UTF-8 box drawing
                await self.session.writeline("╔══════════════════════════════════════════════╗")
                await self.session.writeline("║                                              ║")
                await self.session.writeline("║         PERESTROIKA BBS SYSTEM               ║")
                await self.session.writeline("║                                              ║")
                await self.session.writeline("║         A Modern Retro Experience            ║")
                await self.session.writeline("║                                              ║")
                await self.session.writeline("╚══════════════════════════════════════════════╝")
            elif "437" in self.session.capabilities.encoding or self.session.capabilities.encoding == "cp437":
                # CP437 box drawing (using extended ASCII)
                await self.session.write(b"\xc9" + b"\xcd" * 48 + b"\xbb\r\n")  # ╔═══╗
                await self.session.write(b"\xba" + b" " * 48 + b"\xba\r\n")     # ║   ║
                await self.session.write(b"\xba         PERESTROIKA BBS SYSTEM               \xba\r\n")
                await self.session.write(b"\xba                                                \xba\r\n")
                await self.session.write(b"\xba         A Modern Retro Experience              \xba\r\n")
                await self.session.write(b"\xba" + b" " * 48 + b"\xba\r\n")
                await self.session.write(b"\xc8" + b"\xcd" * 48 + b"\xbc\r\n")  # ╚═══╝
            else:
                # ASCII fallback
                await self.session.writeline("+" + "=" * 48 + "+")
                await self.session.writeline("|                                                |")
                await self.session.writeline("|         PERESTROIKA BBS SYSTEM                |")
                await self.session.writeline("|                                                |")
                await self.session.writeline("|         A Modern Retro Experience              |")
                await self.session.writeline("|                                                |")
                await self.session.writeline("+" + "=" * 48 + "+")

            await self.session.reset_color()
        else:
            # Plain text for non-ANSI terminals
            await self.session.writeline("=" * 50)
            await self.session.writeline("         PERESTROIKA BBS SYSTEM")
            await self.session.writeline("         A Modern Retro Experience")
            await self.session.writeline("=" * 50)

        await self.session.writeline()
        config = get_config()
        await self.session.writeline(config.server.welcome_message if hasattr(config.server, 'welcome_message') else "Welcome!")

    async def show_welcome(self) -> None:
        """Show ASCII-only welcome screen before charset selection

        This must use pure 7-bit ASCII that works on ANY terminal,
        including ancient terminals that don't support extended ASCII.
        """
        # Load the welcome template directly as it's pure ASCII
        from pathlib import Path
        template_path = Path(__file__).parent.parent / "templates" / "templates" / "welcome.j2"

        if template_path.exists():
            with open(template_path, 'r', encoding='ascii', errors='ignore') as f:
                content = f.read()
            # Remove Jinja2 comments
            lines = [line for line in content.split('\n') if not line.strip().startswith('{#')]
            await self.session.write('\r\n'.join(lines))
        else:
            # Fallback if template not found
            await self.session.writeline()
            await self.session.writeline("    +-----------------------+")
            await self.session.writeline("    |   PERESTROIKA BBS     |")
            await self.session.writeline("    |   ===============     |")
            await self.session.writeline("    |                       |")
            await self.session.writeline("    |    Modern Retro       |")
            await self.session.writeline("    |     Experience        |")
            await self.session.writeline("    +-----------------------+")
            await self.session.writeline()
            await self.session.writeline("    Welcome to the system!")

        await self.session.writeline()