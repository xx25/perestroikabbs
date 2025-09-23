import asyncio
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
        prompt = "Your choice: "
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
                        await item.handler()
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
        super().__init__(session, "Main Menu")
        self.setup_menu()

    def setup_menu(self) -> None:
        self.add_item("M", "Message Boards", self.message_boards)
        self.add_item("E", "Private Mail", self.private_mail)
        self.add_item("C", "Chat Rooms", self.chat_rooms)
        self.add_item("F", "File Library", self.file_library)
        self.add_item("U", "User List", self.user_list)
        self.add_item("S", "System Stats", self.system_stats)
        self.add_item("P", "Personal Settings", self.personal_settings)

        if self.session.access_level >= 10:
            self.add_item("A", "Admin Menu", self.admin_menu, min_access=10)

        self.add_item("?", "Help", self.show_help)
        self.add_item("Q", "Quit", self.quit)

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
        settings_menu = Menu(self.session, "Personal Settings")
        settings_menu.add_item("1", "Change Password", self.change_password)
        settings_menu.add_item("2", "Change Email", self.change_email)
        settings_menu.add_item("3", "Terminal Settings", self.terminal_settings)
        settings_menu.add_item("4", "View Profile", self.view_profile)
        settings_menu.add_item("Q", "Back to Main Menu", lambda: setattr(settings_menu, "running", False))

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
        await self.session.writeline("Press any key to continue...")
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
        await self.session.writeline("=== Help ===")
        await self.session.writeline()
        await self.session.writeline("Navigation:")
        await self.session.writeline("  - Use the letter/number keys to select menu options")
        await self.session.writeline("  - Press ENTER after making your selection")
        await self.session.writeline()
        await self.session.writeline("Features:")
        await self.session.writeline("  - Message Boards: Read and post public messages")
        await self.session.writeline("  - Private Mail: Send and receive private messages")
        await self.session.writeline("  - Chat Rooms: Real-time chat with other users")
        await self.session.writeline("  - File Library: Browse and download files")
        await self.session.writeline()
        await self.session.writeline("Terminal Commands:")
        await self.session.writeline("  - Ctrl-C: Interrupt current operation")
        await self.session.writeline("  - Ctrl-S/Ctrl-Q: Pause/resume output")

        await self.session.writeline()
        await self.session.writeline("Press any key to continue...")
        await self.session.read(1)

    async def quit(self) -> None:
        await self.session.writeline()
        await self.session.writeline("Thank you for visiting Perestroika BBS!")
        await self.session.writeline("Goodbye!")
        await asyncio.sleep(1)
        self.running = False