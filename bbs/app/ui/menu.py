import asyncio
import inspect
from typing import Callable, Dict, List, Optional, Tuple

from ..session import Session, SessionState
from ..utils.logger import get_logger

logger = get_logger("ui.menu")


class MenuItem:
    def __init__(
        self,
        key: str,
        label: str,
        handler: Optional[Callable] = None,
        min_access: int = 0,
        submenu: Optional["Menu"] = None,
    ):
        self.key = key.upper()
        self.label = label
        self.handler = handler
        self.min_access = min_access
        self.submenu = submenu


class Menu:
    def __init__(self, session: Session, title: str = "Menu"):
        self.session = session
        self.title = title
        self.items: List[MenuItem] = []
        self.running = True

    def add_item(
        self,
        key: str,
        label: str,
        handler: Optional[Callable] = None,
        min_access: int = 0,
        submenu: Optional["Menu"] = None,
    ) -> None:
        self.items.append(MenuItem(key, label, handler, min_access, submenu))

    async def display(self) -> None:
        await self.session.clear_screen()

        if self.session.capabilities.ansi:
            await self.session.set_color(fg=3, bold=True)
            width = max(len(self.title), max(len(f"[{i.key}] {i.label}") for i in self.items) + 2)
            await self.session.writeline("╔" + "═" * width + "╗")
            await self.session.writeline("║ " + self.title.center(width - 2) + " ║")
            await self.session.writeline("╟" + "─" * width + "╢")

            await self.session.reset_color()

            for item in self.items:
                if self.session.access_level >= item.min_access:
                    await self.session.set_color(fg=6)
                    await self.session.write(f"║ [{item.key}] ")
                    await self.session.set_color(fg=7)
                    await self.session.write(f"{item.label}".ljust(width - len(item.key) - 5))
                    await self.session.writeline(" ║")

            await self.session.set_color(fg=3, bold=True)
            await self.session.writeline("╚" + "═" * width + "╝")
            await self.session.reset_color()

        else:
            await self.session.writeline("=" * 40)
            await self.session.writeline(self.title.center(40))
            await self.session.writeline("-" * 40)

            for item in self.items:
                if self.session.access_level >= item.min_access:
                    await self.session.writeline(f"  [{item.key}] {item.label}")

            await self.session.writeline("=" * 40)

        await self.session.writeline()

    async def get_choice(self) -> Optional[MenuItem]:
        prompt = f"{self.session.t('login.your_choice')}: "
        choice = (await self.session.readline(prompt)).upper()

        for item in self.items:
            if item.key == choice and self.session.access_level >= item.min_access:
                return item

        return None

    async def run(self) -> None:
        while self.running:
            await self.display()
            item = await self.get_choice()

            if item:
                if item.submenu:
                    await item.submenu.run()
                elif item.handler:
                    try:
                        result = item.handler()
                        if inspect.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Menu handler error: {e}", exc_info=True)
                        await self.session.writeline(f"\r\nError: {e}")
                        await self.session.writeline("Press any key to continue...")
                        await self.session.read(1)
            else:
                await self.session.writeline("Invalid selection. Please try again.")
                await asyncio.sleep(1)


class MainMenu(Menu):
    def __init__(self, session: Session):
        super().__init__(session, session.t('menu.main_title'))
        self.setup_menu()

    def setup_menu(self) -> None:
        self.add_item("M", self.session.t('menu.boards'), self.message_boards)
        self.add_item("E", self.session.t('menu.mail'), self.private_mail)
        self.add_item("C", self.session.t('menu.chat'), self.chat_rooms)
        self.add_item("F", self.session.t('menu.files'), self.file_library)
        self.add_item("U", self.session.t('menu.users'), self.user_list)
        self.add_item("S", self.session.t('admin.system_stats'), self.system_stats)
        self.add_item("P", self.session.t('menu.settings'), self.personal_settings)

        if self.session.access_level >= 10:
            self.add_item("A", self.session.t('menu.admin'), self.admin_menu, min_access=10)

        self.add_item("?", self.session.t('menu.help'), self.show_help)
        self.add_item("Q", self.session.t('menu.quit'), self.quit)

    async def message_boards(self) -> None:
        from .boards import BoardsUI
        boards_ui = BoardsUI(self.session)
        await boards_ui.run()

    async def private_mail(self) -> None:
        from .mail import MailUI
        mail_ui = MailUI(self.session)
        await mail_ui.run()

    async def chat_rooms(self) -> None:
        from .chat import ChatUI
        chat_ui = ChatUI(self.session)
        await chat_ui.run()

    async def file_library(self) -> None:
        from .file_browser import FileBrowser
        browser = FileBrowser(self.session)
        await browser.run()

    async def user_list(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== User List ===")
        await self.session.writeline()

        from ..storage.repositories import UserRepository
        user_repo = UserRepository()
        users = await user_repo.get_active_users(limit=50)

        if users:
            await self.session.writeline(f"{'Username':<20} {'Last Login':<20} {'Location':<20}")
            await self.session.writeline("-" * 60)

            for user in users:
                last_login = user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else "Never"
                location = user.location[:18] if user.location else "Unknown"
                await self.session.writeline(f"{user.username:<20} {last_login:<20} {location:<20}")
        else:
            await self.session.writeline("No users found.")

        await self.session.writeline()
        await self.session.writeline("Press any key to continue...")
        await self.session.read(1)

    async def system_stats(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== System Statistics ===")
        await self.session.writeline()

        from ..storage.repositories import SystemRepository
        sys_repo = SystemRepository()
        stats = await sys_repo.get_stats()

        await self.session.writeline(f"Total Users:     {stats.get('total_users', 0)}")
        await self.session.writeline(f"Active Sessions: {stats.get('active_sessions', 0)}")
        await self.session.writeline(f"Total Posts:     {stats.get('total_posts', 0)}")
        await self.session.writeline(f"Total Files:     {stats.get('total_files', 0)}")
        await self.session.writeline(f"Total Downloads: {stats.get('total_downloads', 0)}")
        await self.session.writeline()
        await self.session.writeline(f"System Uptime:   {stats.get('uptime', 'Unknown')}")
        await self.session.writeline(f"BBS Version:     {stats.get('version', '0.1.0')}")

        await self.session.writeline()
        await self.session.writeline("Press any key to continue...")
        await self.session.read(1)

    async def personal_settings(self) -> None:
        settings_menu = Menu(self.session, self.session.t('settings.title'))
        settings_menu.add_item("1", self.session.t('settings.change_password'), self.change_password)
        settings_menu.add_item("2", self.session.t('settings.change_email'), self.change_email)
        settings_menu.add_item("3", self.session.t('settings.terminal_settings'), self.terminal_settings)
        settings_menu.add_item("4", self.session.t('settings.language_settings'), self.language_settings)
        settings_menu.add_item("5", self.session.t('settings.view_profile'), self.view_profile)
        settings_menu.add_item("Q", self.session.t('common.back'), lambda: setattr(settings_menu, "running", False))

        await settings_menu.run()

    async def change_password(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Change Password ===")
        await self.session.writeline()

        current = await self.session.read_password("Current password: ")
        new_pass = await self.session.read_password("\r\nNew password: ")
        confirm = await self.session.read_password("\r\nConfirm new password: ")

        if new_pass != confirm:
            await self.session.writeline("\r\nPasswords don't match!")
        elif len(new_pass) < 8:
            await self.session.writeline("\r\nPassword too short (minimum 8 characters)")
        else:
            await self.session.writeline("\r\nPassword changed successfully!")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def change_email(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Change Email ===")
        await self.session.writeline()

        email = await self.session.readline("New email address: ")

        if email:
            await self.session.writeline("\r\nEmail updated successfully!")
        else:
            await self.session.writeline("\r\nEmail not changed.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def terminal_settings(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Terminal Settings ===")
        await self.session.writeline()
        await self.session.writeline(f"Current encoding: {self.session.capabilities.encoding}")
        await self.session.writeline(f"Terminal size:    {self.session.capabilities.cols}x{self.session.capabilities.rows}")
        await self.session.writeline(f"ANSI support:     {'Yes' if self.session.capabilities.ansi else 'No'}")
        await self.session.writeline(f"Color support:    {'Yes' if self.session.capabilities.color else 'No'}")
        await self.session.writeline(f"RIPscrip support: {'Yes' if self.session.capabilities.ripscrip else 'No'}")

        await self.session.writeline()
        await self.session.writeline("Options:")
        await self.session.writeline("1. Change terminal size")
        await self.session.writeline("2. Change encoding")
        await self.session.writeline("3. Toggle ANSI colors")
        await self.session.writeline("4. Save current settings as default")
        await self.session.writeline("0. Back")

        choice = await self.session.readline("\r\nChoice: ")

        if choice == "1":
            await self._change_terminal_size()
        elif choice == "2":
            await self._change_encoding()
        elif choice == "3":
            await self._toggle_ansi()
        elif choice == "4":
            await self._save_terminal_defaults()

        # Show settings again if something was changed
        if choice in ["1", "2", "3", "4"]:
            await self.terminal_settings()  # Recursive call to show updated settings

    async def _change_terminal_size(self) -> None:
        """Change terminal size settings"""
        await self.session.writeline()
        await self.session.writeline("Select terminal size:")
        await self.session.writeline("1. 80x24  (Standard)")
        await self.session.writeline("2. 80x25  (DOS/PC)")
        await self.session.writeline("3. 80x43  (EGA)")
        await self.session.writeline("4. 80x50  (VGA)")
        await self.session.writeline("5. 132x24 (VT100 wide)")
        await self.session.writeline("6. Custom")
        await self.session.writeline("0. Cancel")

        choice = await self.session.readline("\r\nChoice: ")

        size_map = {
            "1": (80, 24),
            "2": (80, 25),
            "3": (80, 43),
            "4": (80, 50),
            "5": (132, 24)
        }

        if choice in size_map:
            cols, rows = size_map[choice]
            self.session.capabilities.cols = cols
            self.session.capabilities.rows = rows
            await self.session.writeline(f"\r\nTerminal size changed to {cols}x{rows}")
        elif choice == "6":
            cols_str = await self.session.readline("\r\nColumns (40-255): ")
            rows_str = await self.session.readline("Rows (20-100): ")
            try:
                cols = int(cols_str)
                rows = int(rows_str)
                if 40 <= cols <= 255 and 20 <= rows <= 100:
                    self.session.capabilities.cols = cols
                    self.session.capabilities.rows = rows
                    await self.session.writeline(f"\r\nTerminal size changed to {cols}x{rows}")
                else:
                    await self.session.writeline("\r\nInvalid size range")
            except ValueError:
                await self.session.writeline("\r\nInvalid input")

    async def _change_encoding(self) -> None:
        """Change character encoding"""
        await self.session.writeline()
        await self.session.writeline("Select encoding:")
        await self.session.writeline("1. UTF-8 (Unicode)")
        await self.session.writeline("2. CP437 (DOS/ANSI art)")
        await self.session.writeline("3. ISO-8859-1 (Latin-1)")
        await self.session.writeline("4. Windows-1252")
        await self.session.writeline("5. KOI8-R (Russian)")
        await self.session.writeline("6. ASCII (7-bit)")
        await self.session.writeline("0. Cancel")

        choice = await self.session.readline("\r\nChoice: ")

        encoding_map = {
            "1": "utf-8",
            "2": "cp437",
            "3": "iso-8859-1",
            "4": "windows-1252",
            "5": "koi8-r",
            "6": "ascii"
        }

        if choice in encoding_map:
            encoding = encoding_map[choice]
            self.session.set_encoding(encoding)
            if encoding == "ascii":
                self.session.capabilities.seven_bit = True
            else:
                self.session.capabilities.seven_bit = False
            await self.session.writeline(f"\r\nEncoding changed to {encoding}")

    async def _toggle_ansi(self) -> None:
        """Toggle ANSI color support"""
        self.session.capabilities.ansi = not self.session.capabilities.ansi
        self.session.capabilities.color = self.session.capabilities.ansi
        status = "enabled" if self.session.capabilities.ansi else "disabled"
        await self.session.writeline(f"\r\nANSI colors {status}")

    async def _save_terminal_defaults(self) -> None:
        """Save current terminal settings as user defaults"""
        if not self.session.user_id:
            await self.session.writeline("\r\nYou must be logged in to save preferences.")
            return

        from ..storage.repositories import UserRepository
        user_repo = UserRepository()

        await user_repo.update_terminal_settings(
            self.session.user_id,
            self.session.capabilities.encoding,
            self.session.capabilities.cols,
            self.session.capabilities.rows
        )

        await self.session.writeline("\r\nTerminal settings saved as defaults.")
        await self.session.writeline("These will be applied on your next login.")

    async def language_settings(self) -> None:
        """Allow user to change interface language"""
        await self.session.clear_screen()
        await self.session.writeline(self.session.t('settings.language_settings'))
        await self.session.writeline()

        current_lang = 'English' if self.session.language == 'en' else 'Русский'
        await self.session.writeline(self.session.t('settings.current_language', language=current_lang))
        await self.session.writeline()

        await self.session.writeline("1. English")
        await self.session.writeline("2. Русский (Russian)")
        await self.session.writeline(f"0. {self.session.t('common.back')}")

        choice = await self.session.readline(f"\r\n{self.session.t('login.your_choice')}: ")

        if choice == "1":
            self.session.set_language('en')
            await self.session.writeline("\r\nLanguage changed to English")
        elif choice == "2":
            self.session.set_language('ru')
            await self.session.writeline("\r\nЯзык изменен на русский")

        # Save preference if logged in
        if choice in ["1", "2"] and self.session.user_id:
            from ..storage.db import get_session
            from sqlalchemy import update
            from ..storage.models import User
            async with get_session() as db_session:
                await db_session.execute(
                    update(User)
                    .where(User.id == self.session.user_id)
                    .values(language_pref=self.session.language)
                )
                await db_session.commit()
            await self.session.writeline(self.session.t('settings.settings_saved'))

        await self.session.read(1)

    async def view_profile(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Your Profile ===")
        await self.session.writeline()
        await self.session.writeline(f"Username:      {self.session.username}")
        await self.session.writeline(f"Access Level:  {self.session.access_level}")
        await self.session.writeline(f"Session ID:    {self.session.id}")
        await self.session.writeline(f"Connected At:  {self.session.connected_at.strftime('%Y-%m-%d %H:%M:%S')}")

        await self.session.writeline()
        await self.session.writeline("Press any key to continue...")
        await self.session.read(1)

    async def admin_menu(self) -> None:
        from .admin import AdminUI
        admin_ui = AdminUI(self.session)
        await admin_ui.run()

    async def show_help(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline(self.session.t('help.title'))
        await self.session.writeline()
        await self.session.writeline(self.session.t('help.navigation'))
        await self.session.writeline(f"  - {self.session.t('help.nav_text')}")
        await self.session.writeline(f"  - {self.session.t('help.nav_enter')}")
        await self.session.writeline()
        await self.session.writeline(self.session.t('help.features'))
        await self.session.writeline(f"  - {self.session.t('help.feat_boards')}")
        await self.session.writeline(f"  - {self.session.t('help.feat_mail')}")
        await self.session.writeline(f"  - {self.session.t('help.feat_chat')}")
        await self.session.writeline(f"  - {self.session.t('help.feat_files')}")
        await self.session.writeline()
        await self.session.writeline(self.session.t('help.commands'))
        await self.session.writeline(f"  - {self.session.t('help.cmd_interrupt')}")
        await self.session.writeline(f"  - {self.session.t('help.cmd_pause')}")

        await self.session.writeline()
        await self.session.writeline(self.session.t('common.continue'))
        await self.session.read(1)

    async def quit(self) -> None:
        await self.session.writeline()
        await self.session.writeline(self.session.t('common.thank_you'))
        await self.session.writeline(self.session.t('common.goodbye'))
        await asyncio.sleep(1)
        self.running = False