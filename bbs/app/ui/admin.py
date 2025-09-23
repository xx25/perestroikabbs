import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from ..session import Session
from ..storage.models import UserStatus
from ..storage.repositories import BoardRepository, FileRepository, SystemRepository, UserRepository
from ..utils.logger import get_logger
from .menu import Menu

logger = get_logger("ui.admin")


class AdminUI:
    """Administrative interface for sysops"""

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository()
        self.board_repo = BoardRepository()
        self.file_repo = FileRepository()
        self.system_repo = SystemRepository()

    async def run(self) -> None:
        if self.session.access_level < 10:
            await self.session.writeline("\r\nAccess denied. Sysop privileges required.")
            await self.session.read(1)
            return

        menu = Menu(self.session, "System Administration")

        menu.add_item("U", "User Management", self.user_management)
        menu.add_item("B", "Board Management", self.board_management)
        menu.add_item("F", "File Area Management", self.file_management)
        menu.add_item("S", "System Statistics", self.system_statistics)
        menu.add_item("L", "View System Logs", self.view_logs)
        menu.add_item("M", "Mass Message", self.mass_message)
        menu.add_item("K", "Kick User", self.kick_user)
        menu.add_item("C", "System Configuration", self.system_config)
        menu.add_item("D", "Database Maintenance", self.database_maintenance)
        menu.add_item("Q", "Back to Main Menu", lambda: setattr(menu, "running", False))

        await menu.run()

    async def user_management(self) -> None:
        menu = Menu(self.session, "User Management")

        menu.add_item("L", "List All Users", self.list_users)
        menu.add_item("E", "Edit User", self.edit_user)
        menu.add_item("D", "Delete User", self.delete_user)
        menu.add_item("B", "Ban/Unban User", self.ban_user)
        menu.add_item("R", "Reset Password", self.reset_password)
        menu.add_item("A", "Access Level Management", self.manage_access_levels)
        menu.add_item("S", "Search Users", self.search_users)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))

        await menu.run()

    async def list_users(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== User List ===")
        await self.session.writeline()

        users = await self.user_repo.get_all_users(limit=100)

        await self.session.writeline(
            f"{'ID':<6} {'Username':<20} {'Access':<7} {'Status':<10} {'Last Login':<20} {'Posts':<6}"
        )
        await self.session.writeline("-" * 80)

        for user in users:
            last_login = user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else "Never"
            status = user.status.value if hasattr(user.status, 'value') else str(user.status)

            await self.session.writeline(
                f"{user.id:<6} {user.username:<20} {user.access_level:<7} "
                f"{status:<10} {last_login:<20} {user.total_posts:<6}"
            )

        await self.session.writeline()
        await self.session.writeline(f"Total users: {len(users)}")
        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def edit_user(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Edit User ===")
        await self.session.writeline()

        username = await self.session.readline("Username to edit: ")
        user = await self.user_repo.get_by_username(username)

        if not user:
            await self.session.writeline(f"\r\nUser '{username}' not found.")
            await self.session.read(1)
            return

        await self.session.writeline(f"\r\nEditing user: {user.username}")
        await self.session.writeline(f"Current access level: {user.access_level}")
        await self.session.writeline(f"Current status: {user.status.value}")
        await self.session.writeline()

        new_access = await self.session.readline("New access level (0-100, blank to skip): ")
        if new_access:
            try:
                level = int(new_access)
                if 0 <= level <= 100:
                    await self.user_repo.update_access_level(user.id, level)
                    await self.session.writeline(f"Access level updated to {level}")
            except ValueError:
                await self.session.writeline("Invalid access level")

        await self.session.writeline("\r\nUser updated successfully.")
        await self.session.read(1)

    async def delete_user(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Delete User ===")
        await self.session.writeline()

        username = await self.session.readline("Username to delete: ")
        user = await self.user_repo.get_by_username(username)

        if not user:
            await self.session.writeline(f"\r\nUser '{username}' not found.")
            await self.session.read(1)
            return

        confirm = await self.session.readline(f"\r\nReally delete user '{username}'? (yes/no): ")

        if confirm.lower() == "yes":
            await self.user_repo.delete_user(user.id)
            await self.session.writeline("\r\nUser deleted successfully.")
        else:
            await self.session.writeline("\r\nDeletion cancelled.")

        await self.session.read(1)

    async def ban_user(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Ban/Unban User ===")
        await self.session.writeline()

        username = await self.session.readline("Username: ")
        user = await self.user_repo.get_by_username(username)

        if not user:
            await self.session.writeline(f"\r\nUser '{username}' not found.")
            await self.session.read(1)
            return

        current_status = user.status.value if hasattr(user.status, 'value') else str(user.status)
        await self.session.writeline(f"\r\nCurrent status: {current_status}")

        if user.status == UserStatus.BANNED:
            action = await self.session.readline("Unban user? (yes/no): ")
            if action.lower() == "yes":
                await self.user_repo.update_status(user.id, UserStatus.ACTIVE)
                await self.session.writeline("\r\nUser unbanned successfully.")
        else:
            action = await self.session.readline("Ban user? (yes/no): ")
            if action.lower() == "yes":
                reason = await self.session.readline("Ban reason: ")
                await self.user_repo.update_status(user.id, UserStatus.BANNED)
                await self.session.writeline("\r\nUser banned successfully.")

        await self.session.read(1)

    async def reset_password(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Reset User Password ===")
        await self.session.writeline()

        username = await self.session.readline("Username: ")
        user = await self.user_repo.get_by_username(username)

        if not user:
            await self.session.writeline(f"\r\nUser '{username}' not found.")
            await self.session.read(1)
            return

        new_password = await self.session.readline("New password (blank for random): ")

        if not new_password:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
            await self.session.writeline(f"\r\nGenerated password: {new_password}")

        from ..security.auth import AuthManager
        auth = AuthManager()
        password_hash = await auth.hash_password(new_password)
        await self.user_repo.update_password(user.id, password_hash)

        await self.session.writeline("\r\nPassword reset successfully.")
        await self.session.read(1)

    async def manage_access_levels(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Access Level Guide ===")
        await self.session.writeline()
        await self.session.writeline("  0 - Guest (read-only)")
        await self.session.writeline("  1 - Normal User")
        await self.session.writeline("  5 - Trusted User")
        await self.session.writeline(" 10 - Moderator")
        await self.session.writeline(" 20 - Co-Sysop")
        await self.session.writeline("100 - Sysop")
        await self.session.writeline()

        username = await self.session.readline("Username to modify: ")
        user = await self.user_repo.get_by_username(username)

        if not user:
            await self.session.writeline(f"\r\nUser '{username}' not found.")
        else:
            await self.session.writeline(f"Current level: {user.access_level}")
            new_level = await self.session.readline("New level: ")

            try:
                level = int(new_level)
                if 0 <= level <= 100:
                    await self.user_repo.update_access_level(user.id, level)
                    await self.session.writeline(f"\r\nAccess level updated to {level}")
                else:
                    await self.session.writeline("\r\nInvalid level (must be 0-100)")
            except ValueError:
                await self.session.writeline("\r\nInvalid input")

        await self.session.read(1)

    async def search_users(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Search Users ===")
        await self.session.writeline()

        query = await self.session.readline("Search for: ")

        if query:
            users = await self.user_repo.search_users(query)

            if users:
                await self.session.writeline(f"\r\nFound {len(users)} user(s):")
                for user in users:
                    await self.session.writeline(f"  - {user.username} (ID: {user.id}, Access: {user.access_level})")
            else:
                await self.session.writeline("\r\nNo users found.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def board_management(self) -> None:
        menu = Menu(self.session, "Board Management")

        menu.add_item("L", "List Boards", self.list_boards)
        menu.add_item("C", "Create Board", self.create_board)
        menu.add_item("E", "Edit Board", self.edit_board)
        menu.add_item("D", "Delete Board", self.delete_board)
        menu.add_item("P", "Prune Old Posts", self.prune_posts)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))

        await menu.run()

    async def list_boards(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Message Boards ===")
        await self.session.writeline()

        boards = await self.board_repo.get_all_boards(user_access_level=100)

        await self.session.writeline(
            f"{'ID':<5} {'Name':<20} {'Posts':<8} {'Read':<5} {'Write':<5} {'Last Post':<20}"
        )
        await self.session.writeline("-" * 70)

        for board in boards:
            last_post = board.last_post_at.strftime("%Y-%m-%d %H:%M") if board.last_post_at else "Never"
            await self.session.writeline(
                f"{board.id:<5} {board.name:<20} {board.post_count:<8} "
                f"{board.min_read_access:<5} {board.min_write_access:<5} {last_post:<20}"
            )

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def create_board(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Create New Board ===")
        await self.session.writeline()

        name = await self.session.readline("Board name: ")
        if not name:
            await self.session.writeline("Board creation cancelled.")
            await self.session.read(1)
            return

        description = await self.session.readline("Description: ")
        min_read = await self.session.readline("Min read access (0): ") or "0"
        min_write = await self.session.readline("Min write access (1): ") or "1"

        try:
            board = await self.board_repo.create_board(
                name=name,
                description=description,
                min_read=int(min_read),
                min_write=int(min_write)
            )
            await self.session.writeline(f"\r\nBoard '{name}' created successfully.")
        except Exception as e:
            await self.session.writeline(f"\r\nError creating board: {e}")

        await self.session.read(1)

    async def edit_board(self) -> None:
        await self.session.writeline("\r\nBoard editing not yet implemented.")
        await self.session.read(1)

    async def delete_board(self) -> None:
        await self.session.writeline("\r\nBoard deletion not yet implemented.")
        await self.session.read(1)

    async def prune_posts(self) -> None:
        await self.session.writeline("\r\nPost pruning not yet implemented.")
        await self.session.read(1)

    async def file_management(self) -> None:
        await self.session.writeline("\r\nFile area management not yet implemented.")
        await self.session.read(1)

    async def system_statistics(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== System Statistics ===")
        await self.session.writeline()

        stats = await self.system_repo.get_detailed_stats()

        await self.session.writeline(f"Total Users:        {stats.get('total_users', 0)}")
        await self.session.writeline(f"Active Users:       {stats.get('active_users', 0)}")
        await self.session.writeline(f"Banned Users:       {stats.get('banned_users', 0)}")
        await self.session.writeline(f"Active Sessions:    {stats.get('active_sessions', 0)}")
        await self.session.writeline()
        await self.session.writeline(f"Total Posts:        {stats.get('total_posts', 0)}")
        await self.session.writeline(f"Total Boards:       {stats.get('total_boards', 0)}")
        await self.session.writeline(f"Total Files:        {stats.get('total_files', 0)}")
        await self.session.writeline(f"Total Downloads:    {stats.get('total_downloads', 0)}")
        await self.session.writeline(f"Total Uploads:      {stats.get('total_uploads', 0)}")
        await self.session.writeline()
        await self.session.writeline(f"Storage Used:       {stats.get('storage_used', 'Unknown')}")
        await self.session.writeline(f"Database Size:      {stats.get('db_size', 'Unknown')}")
        await self.session.writeline()
        await self.session.writeline(f"System Uptime:      {stats.get('uptime', 'Unknown')}")
        await self.session.writeline(f"BBS Version:        {stats.get('version', '0.1.0')}")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def view_logs(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== System Logs ===")
        await self.session.writeline()

        # Show recent log entries
        log_file = "/var/log/bbs/perestroika.log"
        try:
            from pathlib import Path
            if Path(log_file).exists():
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-50:]  # Last 50 lines
                    for line in lines:
                        await self.session.writeline(line.rstrip())
            else:
                await self.session.writeline("Log file not found.")
        except Exception as e:
            await self.session.writeline(f"Error reading logs: {e}")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def mass_message(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Send Mass Message ===")
        await self.session.writeline()

        await self.session.writeline("Enter message (end with '.' on a line by itself):")
        message_lines = []
        while True:
            line = await self.session.readline()
            if line == ".":
                break
            message_lines.append(line)

        if message_lines:
            message = "\n".join(message_lines)
            # TODO: Implement actual mass message sending
            await self.session.writeline("\r\nMessage would be sent to all users:")
            await self.session.writeline(message)
            await self.session.writeline("\r\n(Feature not yet fully implemented)")

        await self.session.read(1)

    async def kick_user(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Kick User ===")
        await self.session.writeline()

        # Show active sessions
        from ..telnet_server import TelnetServer
        # Note: This would need access to the server's session list
        await self.session.writeline("Active sessions:")
        await self.session.writeline("(Feature not yet fully implemented)")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def system_config(self) -> None:
        await self.session.writeline("\r\nSystem configuration editor not yet implemented.")
        await self.session.writeline("Please edit config.toml manually.")
        await self.session.read(1)

    async def database_maintenance(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Database Maintenance ===")
        await self.session.writeline()

        await self.session.writeline("1. Vacuum database")
        await self.session.writeline("2. Rebuild indexes")
        await self.session.writeline("3. Clean orphaned records")
        await self.session.writeline("4. Export backup")

        choice = await self.session.readline("\r\nChoice: ")

        if choice == "1":
            await self.session.writeline("\r\nVacuuming database...")
            # TODO: Implement actual vacuum
            await self.session.writeline("Database vacuum would be performed here.")
        elif choice == "2":
            await self.session.writeline("\r\nRebuilding indexes...")
            await self.session.writeline("Index rebuild would be performed here.")
        elif choice == "3":
            await self.session.writeline("\r\nCleaning orphaned records...")
            await self.session.writeline("Orphan cleanup would be performed here.")
        elif choice == "4":
            await self.session.writeline("\r\nExporting backup...")
            await self.session.writeline("Backup export would be performed here.")

        await self.session.read(1)