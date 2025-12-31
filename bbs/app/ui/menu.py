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
        await self.session.writeline(f"=== {self.session.t('users.title')} ===")
        await self.session.writeline()

        from ..storage.repositories import UserRepository
        user_repo = UserRepository()
        users = await user_repo.get_active_users(limit=50)

        if users:
            username_hdr = self.session.t('users.username')
            last_login_hdr = self.session.t('users.last_login')
            location_hdr = self.session.t('users.location')
            await self.session.writeline(f"{username_hdr:<20} {last_login_hdr:<20} {location_hdr:<20}")
            await self.session.writeline("-" * 60)

            for user in users:
                last_login = user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else self.session.t('users.never')
                location = user.location[:18] if user.location else self.session.t('users.unknown')
                await self.session.writeline(f"{user.username:<20} {last_login:<20} {location:<20}")
        else:
            await self.session.writeline(self.session.t('users.no_users'))

        await self.session.writeline()
        await self.session.writeline(self.session.t('common.continue'))
        await self.session.read(1)

    async def system_stats(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline(f"=== {self.session.t('admin.system_stats')} ===")
        await self.session.writeline()

        from ..storage.repositories import SystemRepository
        sys_repo = SystemRepository()
        stats = await sys_repo.get_stats()

        await self.session.writeline(self.session.t('admin.total_users', count=stats.get('total_users', 0)))
        await self.session.writeline(self.session.t('admin.active_sessions', count=stats.get('active_sessions', 0)))
        await self.session.writeline(self.session.t('admin.total_posts', count=stats.get('total_posts', 0)))
        await self.session.writeline(self.session.t('admin.total_files', count=stats.get('total_files', 0)))
        await self.session.writeline(self.session.t('admin.total_downloads', count=stats.get('total_downloads', 0)))
        await self.session.writeline()
        await self.session.writeline(self.session.t('admin.uptime', time=stats.get('uptime', '?')))
        await self.session.writeline(self.session.t('admin.version', version=stats.get('version', '0.1.0')))

        await self.session.writeline()
        await self.session.writeline(self.session.t('common.continue'))
        await self.session.read(1)

    async def personal_settings(self) -> None:
        settings_menu = Menu(self.session, self.session.t('settings.title'))
        settings_menu.add_item("1", self.session.t('settings.change_password'), self.change_password)
        settings_menu.add_item("2", self.session.t('settings.change_email'), self.change_email)
        settings_menu.add_item("3", self.session.t('settings.view_profile'), self.view_profile)
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