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
        menu.add_item("I", "IP Ban Management", self.ip_ban_management)
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
        await self.session.clear_screen()
        await self.session.writeline("=== Edit Board ===")
        await self.session.writeline()

        # List all boards
        boards = await self.board_repo.get_all_boards(100)  # Admin access
        if not boards:
            await self.session.writeline("No boards found.")
            await self.session.read(1)
            return

        await self.session.writeline("Available boards:")
        for i, board in enumerate(boards, 1):
            await self.session.writeline(
                f"{i}. {board.name} (Read: {board.min_read_access}, "
                f"Write: {board.min_write_access})"
            )

        await self.session.writeline()
        choice = await self.session.readline("Select board to edit (0 to cancel): ")

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(boards):
                return
        except (ValueError, IndexError):
            return

        board = boards[idx]
        await self.session.writeline(f"\r\nEditing: {board.name}")
        await self.session.writeline(f"Current description: {board.description or '(none)'}")
        await self.session.writeline(f"Current read access: {board.min_read_access}")
        await self.session.writeline(f"Current write access: {board.min_write_access}")
        await self.session.writeline()

        # Edit fields
        new_name = await self.session.readline(f"New name [{board.name}]: ")
        if not new_name:
            new_name = board.name

        new_desc = await self.session.readline(f"New description [{board.description or ''}]: ")
        if not new_desc and board.description:
            new_desc = board.description

        new_read = await self.session.readline(f"Min read access [{board.min_read_access}]: ")
        try:
            new_read = int(new_read) if new_read else board.min_read_access
        except ValueError:
            new_read = board.min_read_access

        new_write = await self.session.readline(f"Min write access [{board.min_write_access}]: ")
        try:
            new_write = int(new_write) if new_write else board.min_write_access
        except ValueError:
            new_write = board.min_write_access

        # Update board
        try:
            from ..storage.db import get_session
            from sqlalchemy import update
            async with get_session() as db_session:
                await db_session.execute(
                    update(Board)
                    .where(Board.id == board.id)
                    .values(
                        name=new_name,
                        description=new_desc,
                        min_read_access=new_read,
                        min_write_access=new_write
                    )
                )
                await db_session.commit()
            await self.session.writeline("\r\nBoard updated successfully!")
        except Exception as e:
            await self.session.writeline(f"\r\nError updating board: {e}")

        await self.session.read(1)

    async def delete_board(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Delete Board ===")
        await self.session.writeline()
        await self.session.writeline("WARNING: This will delete the board and ALL its posts!")
        await self.session.writeline()

        # List all boards
        boards = await self.board_repo.get_all_boards(100)  # Admin access
        if not boards:
            await self.session.writeline("No boards found.")
            await self.session.read(1)
            return

        await self.session.writeline("Available boards:")
        for i, board in enumerate(boards, 1):
            await self.session.writeline(
                f"{i}. {board.name} ({board.post_count} posts)"
            )

        await self.session.writeline()
        choice = await self.session.readline("Select board to DELETE (0 to cancel): ")

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(boards):
                return
        except (ValueError, IndexError):
            return

        board = boards[idx]
        await self.session.writeline(f"\r\nAbout to delete: {board.name}")
        await self.session.writeline(f"This will remove {board.post_count} posts!")

        confirm = await self.session.readline("Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            await self.session.writeline("\r\nCancelled.")
            await self.session.read(1)
            return

        # Delete board
        try:
            from ..storage.db import get_session
            async with get_session() as db_session:
                board_to_delete = await db_session.get(Board, board.id)
                if board_to_delete:
                    await db_session.delete(board_to_delete)
                    await db_session.commit()
                    await self.session.writeline("\r\nBoard deleted successfully!")
                else:
                    await self.session.writeline("\r\nBoard not found!")
        except Exception as e:
            await self.session.writeline(f"\r\nError deleting board: {e}")

        await self.session.read(1)

    async def prune_posts(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Prune Old Posts ===")
        await self.session.writeline()

        await self.session.writeline("Prune posts older than:")
        await self.session.writeline("1. 30 days")
        await self.session.writeline("2. 60 days")
        await self.session.writeline("3. 90 days")
        await self.session.writeline("4. 180 days")
        await self.session.writeline("5. 1 year")
        await self.session.writeline("0. Cancel")

        choice = await self.session.readline("\r\nChoice: ")

        days_map = {
            "1": 30,
            "2": 60,
            "3": 90,
            "4": 180,
            "5": 365
        }

        if choice not in days_map:
            return

        days = days_map[choice]

        # Count posts to be deleted
        from datetime import datetime, timedelta
        from ..storage.db import get_session
        from sqlalchemy import select, delete, func

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        try:
            async with get_session() as db_session:
                # Count posts to be deleted
                count_result = await db_session.execute(
                    select(func.count(Post.id))
                    .where(Post.created_at < cutoff_date)
                )
                post_count = count_result.scalar() or 0

                if post_count == 0:
                    await self.session.writeline(f"\r\nNo posts older than {days} days found.")
                    await self.session.read(1)
                    return

                await self.session.writeline(f"\r\nFound {post_count} posts to delete.")
                confirm = await self.session.readline("Type 'PRUNE' to confirm: ")

                if confirm != "PRUNE":
                    await self.session.writeline("\r\nCancelled.")
                    await self.session.read(1)
                    return

                # Delete old posts
                await db_session.execute(
                    delete(Post).where(Post.created_at < cutoff_date)
                )
                await db_session.commit()

                await self.session.writeline(f"\r\nPruned {post_count} old posts.")

        except Exception as e:
            await self.session.writeline(f"\r\nError pruning posts: {e}")

        await self.session.read(1)

    async def file_management(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== File Area Management ===")
        await self.session.writeline()

        await self.session.writeline("1. Create file area")
        await self.session.writeline("2. Edit file area")
        await self.session.writeline("3. Delete file area")
        await self.session.writeline("4. List orphaned files")
        await self.session.writeline("5. Clean duplicate files")
        await self.session.writeline("6. Transfer audit log")
        await self.session.writeline("0. Back")

        choice = await self.session.readline("\r\nChoice: ")

        if choice == "1":
            await self._create_file_area()
        elif choice == "2":
            await self._edit_file_area()
        elif choice == "3":
            await self._delete_file_area()
        elif choice == "4":
            await self._list_orphaned_files()
        elif choice == "5":
            await self._clean_duplicate_files()
        elif choice == "6":
            await self._transfer_audit_log()

    async def _create_file_area(self) -> None:
        await self.session.writeline("\r\n=== Create File Area ===")

        name = await self.session.readline("Area name: ")
        if not name:
            return

        desc = await self.session.readline("Description: ")
        path = await self.session.readline("Path (relative to files dir): ")

        min_access = await self.session.readline("Min access level [1]: ")
        try:
            min_access = int(min_access) if min_access else 1
        except ValueError:
            min_access = 1

        try:
            from ..storage.db import get_session
            from ..storage.models import FileArea
            async with get_session() as db_session:
                area = FileArea(
                    name=name,
                    description=desc,
                    path=path or name.lower().replace(" ", "_"),
                    min_access_level=min_access
                )
                db_session.add(area)
                await db_session.commit()
                await self.session.writeline("\r\nFile area created successfully!")
        except Exception as e:
            await self.session.writeline(f"\r\nError creating area: {e}")

        await self.session.read(1)

    async def _edit_file_area(self) -> None:
        await self.session.writeline("\r\n=== Edit File Area ===")

        # List areas
        from ..storage.db import get_session
        from ..storage.models import FileArea
        from sqlalchemy import select

        async with get_session() as db_session:
            result = await db_session.execute(select(FileArea).order_by(FileArea.name))
            areas = result.scalars().all()

        if not areas:
            await self.session.writeline("No file areas found.")
            await self.session.read(1)
            return

        for i, area in enumerate(areas, 1):
            await self.session.writeline(f"{i}. {area.name} - {area.description}")

        choice = await self.session.readline("\r\nSelect area (0 to cancel): ")
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(areas):
                return
        except ValueError:
            return

        area = areas[idx]
        await self.session.writeline(f"\r\nEditing: {area.name}")

        new_name = await self.session.readline(f"Name [{area.name}]: ")
        new_desc = await self.session.readline(f"Description [{area.description}]: ")
        new_access = await self.session.readline(f"Min access [{area.min_access_level}]: ")

        try:
            from sqlalchemy import update
            async with get_session() as db_session:
                await db_session.execute(
                    update(FileArea)
                    .where(FileArea.id == area.id)
                    .values(
                        name=new_name or area.name,
                        description=new_desc or area.description,
                        min_access_level=int(new_access) if new_access else area.min_access_level
                    )
                )
                await db_session.commit()
                await self.session.writeline("\r\nArea updated successfully!")
        except Exception as e:
            await self.session.writeline(f"\r\nError updating area: {e}")

        await self.session.read(1)

    async def _delete_file_area(self) -> None:
        await self.session.writeline("\r\n=== Delete File Area ===")
        await self.session.writeline("WARNING: Files will be orphaned!")

        # List areas
        from ..storage.db import get_session
        from ..storage.models import FileArea
        from sqlalchemy import select, func

        async with get_session() as db_session:
            result = await db_session.execute(select(FileArea).order_by(FileArea.name))
            areas = result.scalars().all()

        if not areas:
            await self.session.writeline("No file areas found.")
            await self.session.read(1)
            return

        for i, area in enumerate(areas, 1):
            # Count files in area
            count_result = await db_session.execute(
                select(func.count(File.id)).where(File.area_id == area.id)
            )
            file_count = count_result.scalar() or 0
            await self.session.writeline(f"{i}. {area.name} ({file_count} files)")

        choice = await self.session.readline("\r\nSelect area to DELETE (0 to cancel): ")
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(areas):
                return
        except ValueError:
            return

        area = areas[idx]
        confirm = await self.session.readline("Type 'DELETE' to confirm: ")
        if confirm != "DELETE":
            return

        try:
            async with get_session() as db_session:
                area_to_delete = await db_session.get(FileArea, area.id)
                if area_to_delete:
                    await db_session.delete(area_to_delete)
                    await db_session.commit()
                    await self.session.writeline("\r\nArea deleted successfully!")
        except Exception as e:
            await self.session.writeline(f"\r\nError deleting area: {e}")

        await self.session.read(1)

    async def _list_orphaned_files(self) -> None:
        await self.session.writeline("\r\n=== Orphaned Files ===")

        from ..storage.db import get_session
        from sqlalchemy import select

        async with get_session() as db_session:
            result = await db_session.execute(
                select(File).where(File.area_id == None)
            )
            orphans = result.scalars().all()

        if not orphans:
            await self.session.writeline("No orphaned files found.")
        else:
            await self.session.writeline(f"Found {len(orphans)} orphaned files:")
            for f in orphans[:20]:  # Show first 20
                await self.session.writeline(f"  - {f.filename} ({f.size} bytes)")
            if len(orphans) > 20:
                await self.session.writeline(f"  ... and {len(orphans) - 20} more")

        await self.session.read(1)

    async def _clean_duplicate_files(self) -> None:
        await self.session.writeline("\r\n=== Clean Duplicate Files ===")

        from ..storage.db import get_session
        from sqlalchemy import select, func

        async with get_session() as db_session:
            # Find duplicates by checksum
            subq = select(
                File.checksum,
                func.count(File.id).label('count')
            ).group_by(File.checksum).having(func.count(File.id) > 1).subquery()

            result = await db_session.execute(
                select(File)
                .join(subq, File.checksum == subq.c.checksum)
                .order_by(File.checksum, File.created_at)
            )
            duplicates = result.scalars().all()

        if not duplicates:
            await self.session.writeline("No duplicate files found.")
            await self.session.read(1)
            return

        # Group by checksum
        by_checksum = {}
        for f in duplicates:
            if f.checksum not in by_checksum:
                by_checksum[f.checksum] = []
            by_checksum[f.checksum].append(f)

        await self.session.writeline(f"Found {len(by_checksum)} sets of duplicates:")
        for checksum, files in list(by_checksum.items())[:10]:
            await self.session.writeline(f"\r\nChecksum: {checksum[:16]}...")
            for f in files:
                await self.session.writeline(f"  - {f.filename} (area: {f.area_id})")

        await self.session.writeline("\r\n(Feature to auto-clean not yet implemented)")
        await self.session.read(1)

    async def _transfer_audit_log(self) -> None:
        """Display transfer audit log"""
        await self.session.clear_screen()
        await self.session.writeline("=== Transfer Audit Log ===")
        await self.session.writeline()

        try:
            from ..storage.db import get_session
            from ..storage.models import Transfer, User, File
            from sqlalchemy import select, desc
            from datetime import datetime, timedelta

            # Options for filtering
            await self.session.writeline("View transfers from:")
            await self.session.writeline("1. Last 24 hours")
            await self.session.writeline("2. Last 7 days")
            await self.session.writeline("3. Last 30 days")
            await self.session.writeline("4. All time")
            await self.session.writeline("5. By specific user")

            choice = await self.session.readline("\r\nChoice: ")

            async with get_session() as db_session:
                query = select(Transfer, User, File).join(
                    User, Transfer.user_id == User.id
                ).join(
                    File, Transfer.file_id == File.id
                ).order_by(desc(Transfer.started_at))

                # Apply time filter
                if choice == "1":
                    cutoff = datetime.utcnow() - timedelta(days=1)
                    query = query.where(Transfer.started_at >= cutoff)
                    filter_desc = "Last 24 hours"
                elif choice == "2":
                    cutoff = datetime.utcnow() - timedelta(days=7)
                    query = query.where(Transfer.started_at >= cutoff)
                    filter_desc = "Last 7 days"
                elif choice == "3":
                    cutoff = datetime.utcnow() - timedelta(days=30)
                    query = query.where(Transfer.started_at >= cutoff)
                    filter_desc = "Last 30 days"
                elif choice == "4":
                    filter_desc = "All time"
                elif choice == "5":
                    username = await self.session.readline("\r\nUsername: ")
                    user_result = await db_session.execute(
                        select(User).where(User.username == username)
                    )
                    target_user = user_result.scalar_one_or_none()
                    if not target_user:
                        await self.session.writeline(f"\r\nUser '{username}' not found.")
                        await self.session.read(1)
                        return
                    query = query.where(Transfer.user_id == target_user.id)
                    filter_desc = f"User: {username}"
                else:
                    filter_desc = "All time"

                # Limit results
                query = query.limit(100)

                result = await db_session.execute(query)
                transfers = result.all()

                if not transfers:
                    await self.session.writeline(f"\r\nNo transfers found ({filter_desc})")
                else:
                    await self.session.writeline(f"\r\nShowing transfers ({filter_desc}):")
                    await self.session.writeline()

                    # Header
                    await self.session.writeline(
                        f"{'Time':<20} {'User':<15} {'Type':<4} {'Protocol':<8} "
                        f"{'File':<25} {'Size':<10} {'Status':<10}"
                    )
                    await self.session.writeline("-" * 100)

                    for transfer, user, file in transfers:
                        time_str = transfer.started_at.strftime("%Y-%m-%d %H:%M:%S")
                        type_str = "UP" if transfer.is_upload else "DN"
                        protocol = transfer.protocol or "unknown"
                        filename = file.filename[:24] if len(file.filename) > 24 else file.filename
                        size_str = self._format_size(transfer.bytes_transferred)

                        if transfer.completed:
                            status = "Complete"
                        elif transfer.error:
                            status = "Failed"
                        else:
                            status = "Partial"

                        await self.session.writeline(
                            f"{time_str:<20} {user.username:<15} {type_str:<4} "
                            f"{protocol:<8} {filename:<25} {size_str:<10} {status:<10}"
                        )

                        if transfer.error:
                            await self.session.writeline(f"  Error: {transfer.error[:70]}")

                    # Summary statistics
                    await self.session.writeline()
                    await self.session.writeline("=== Summary ===")

                    # Count uploads/downloads
                    uploads = [t for t, _, _ in transfers if t.is_upload]
                    downloads = [t for t, _, _ in transfers if not t.is_upload]
                    completed = [t for t, _, _ in transfers if t.completed]
                    failed = [t for t, _, _ in transfers if t.error]

                    await self.session.writeline(f"Total transfers: {len(transfers)}")
                    await self.session.writeline(f"  Uploads: {len(uploads)}")
                    await self.session.writeline(f"  Downloads: {len(downloads)}")
                    await self.session.writeline(f"  Completed: {len(completed)}")
                    await self.session.writeline(f"  Failed: {len(failed)}")

                    # Total bytes
                    total_bytes = sum(t.bytes_transferred for t, _, _ in transfers if t.bytes_transferred)
                    await self.session.writeline(f"  Total data: {self._format_size(total_bytes)}")

        except Exception as e:
            await self.session.writeline(f"\r\nError loading transfer log: {e}")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    def _format_size(self, bytes_size: int) -> str:
        """Format byte size for display"""
        if bytes_size is None:
            return "Unknown"
        if bytes_size < 1024:
            return f"{bytes_size}B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f}KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f}MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.1f}GB"

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

        # Get active sessions from database
        try:
            from ..storage.db import get_session
            from ..storage.models import Session as SessionModel, User
            from sqlalchemy import select, and_
            from datetime import datetime

            async with get_session() as db_session:
                # Get active sessions (sessions without ended_at)
                result = await db_session.execute(
                    select(SessionModel, User)
                    .join(User, SessionModel.user_id == User.id)
                    .where(SessionModel.ended_at == None)
                    .order_by(SessionModel.started_at.desc())
                )
                active_sessions = result.all()

                if not active_sessions:
                    await self.session.writeline("No active sessions found.")
                    await self.session.read(1)
                    return

                await self.session.writeline("Active sessions:")
                for i, (sess, user) in enumerate(active_sessions, 1):
                    duration = datetime.utcnow() - sess.started_at
                    mins = int(duration.total_seconds() / 60)
                    await self.session.writeline(
                        f"{i}. {user.username:15} from {sess.remote_addr:15} "
                        f"({mins} minutes)"
                    )

                await self.session.writeline()
                choice = await self.session.readline("Select user to kick (0 to cancel): ")

                try:
                    idx = int(choice) - 1
                    if idx < 0 or idx >= len(active_sessions):
                        return
                except ValueError:
                    return

                sess_to_end, user_to_kick = active_sessions[idx]

                # Mark session as ended
                sess_to_end.ended_at = datetime.utcnow()
                await db_session.commit()

                await self.session.writeline(
                    f"\r\nSession for {user_to_kick.username} has been marked as ended."
                )
                await self.session.writeline(
                    "Note: The actual connection termination requires server-side integration."
                )

        except Exception as e:
            await self.session.writeline(f"\r\nError managing sessions: {e}")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def ip_ban_management(self) -> None:
        """Manage IP bans"""
        await self.session.clear_screen()
        await self.session.writeline("=== IP Ban Management ===")
        await self.session.writeline()

        menu = Menu(self.session, "IP Ban Options")
        menu.add_item("L", "List Banned IPs", self._list_banned_ips)
        menu.add_item("A", "Add IP Ban", self._add_ip_ban)
        menu.add_item("R", "Remove IP Ban", self._remove_ip_ban)
        menu.add_item("C", "Check IP Status", self._check_ip_status)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))
        await menu.run()

    async def _list_banned_ips(self) -> None:
        """List all banned IPs"""
        await self.session.clear_screen()
        await self.session.writeline("=== Banned IPs ===")
        await self.session.writeline()

        try:
            # Get rate limiter instance (would need to be passed or accessed globally)
            from ..security.auth import RateLimiter
            # This is a simplified example - in production, you'd maintain a global rate limiter
            limiter = RateLimiter()

            # Load bans from file
            ban_file = "/var/lib/bbs/ip_bans.json"
            await limiter.load_bans(ban_file)

            banned_ips = await limiter.get_banned_ips()

            if not banned_ips:
                await self.session.writeline("No IPs are currently banned.")
            else:
                await self.session.writeline(f"{'IP Address':<20} {'Type':<12} {'Expires':<30}")
                await self.session.writeline("-" * 65)

                for ip, info in banned_ips.items():
                    if info['type'] == 'permanent':
                        expires = "Never"
                    else:
                        from datetime import datetime
                        expires = datetime.fromtimestamp(info['expires']).strftime("%Y-%m-%d %H:%M:%S")
                        expires += f" ({info['remaining']}s left)"

                    await self.session.writeline(f"{ip:<20} {info['type']:<12} {expires:<30}")

        except Exception as e:
            await self.session.writeline(f"Error listing bans: {e}")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def _add_ip_ban(self) -> None:
        """Add a new IP ban"""
        await self.session.clear_screen()
        await self.session.writeline("=== Add IP Ban ===")
        await self.session.writeline()

        ip = await self.session.readline("IP address to ban: ")
        if not ip:
            return

        await self.session.writeline("\r\nBan duration:")
        await self.session.writeline("1. 1 hour")
        await self.session.writeline("2. 24 hours")
        await self.session.writeline("3. 7 days")
        await self.session.writeline("4. 30 days")
        await self.session.writeline("5. Permanent")

        choice = await self.session.readline("\r\nChoice: ")

        duration_map = {
            "1": 3600,        # 1 hour
            "2": 86400,       # 24 hours
            "3": 604800,      # 7 days
            "4": 2592000,     # 30 days
            "5": None         # Permanent
        }

        if choice not in duration_map:
            await self.session.writeline("\r\nInvalid choice.")
            await self.session.read(1)
            return

        try:
            from ..security.auth import RateLimiter
            limiter = RateLimiter()

            # Load existing bans
            ban_file = "/var/lib/bbs/ip_bans.json"
            await limiter.load_bans(ban_file)

            # Add the ban
            await limiter.ban_ip(ip, duration_map[choice])

            # Save bans
            await limiter.save_bans(ban_file)

            if duration_map[choice] is None:
                await self.session.writeline(f"\r\nIP {ip} permanently banned.")
            else:
                await self.session.writeline(f"\r\nIP {ip} banned for {duration_map[choice]} seconds.")

        except Exception as e:
            await self.session.writeline(f"\r\nError adding ban: {e}")

        await self.session.read(1)

    async def _remove_ip_ban(self) -> None:
        """Remove an IP ban"""
        await self.session.clear_screen()
        await self.session.writeline("=== Remove IP Ban ===")
        await self.session.writeline()

        ip = await self.session.readline("IP address to unban: ")
        if not ip:
            return

        try:
            from ..security.auth import RateLimiter
            limiter = RateLimiter()

            # Load existing bans
            ban_file = "/var/lib/bbs/ip_bans.json"
            await limiter.load_bans(ban_file)

            # Remove the ban
            if await limiter.unban_ip(ip):
                await self.session.writeline(f"\r\nIP {ip} has been unbanned.")
                # Save bans
                await limiter.save_bans(ban_file)
            else:
                await self.session.writeline(f"\r\nIP {ip} was not banned.")

        except Exception as e:
            await self.session.writeline(f"\r\nError removing ban: {e}")

        await self.session.read(1)

    async def _check_ip_status(self) -> None:
        """Check if an IP is banned"""
        await self.session.clear_screen()
        await self.session.writeline("=== Check IP Status ===")
        await self.session.writeline()

        ip = await self.session.readline("IP address to check: ")
        if not ip:
            return

        try:
            from ..security.auth import RateLimiter
            limiter = RateLimiter()

            # Load existing bans
            ban_file = "/var/lib/bbs/ip_bans.json"
            await limiter.load_bans(ban_file)

            if await limiter.is_banned(ip):
                banned_ips = await limiter.get_banned_ips()
                if ip in banned_ips:
                    info = banned_ips[ip]
                    await self.session.writeline(f"\r\nIP {ip} is BANNED")
                    await self.session.writeline(f"Type: {info['type']}")
                    if info['expires']:
                        from datetime import datetime
                        expires = datetime.fromtimestamp(info['expires']).strftime("%Y-%m-%d %H:%M:%S")
                        await self.session.writeline(f"Expires: {expires}")
                        await self.session.writeline(f"Time remaining: {info['remaining']} seconds")
            else:
                await self.session.writeline(f"\r\nIP {ip} is NOT banned")

        except Exception as e:
            await self.session.writeline(f"\r\nError checking IP: {e}")

        await self.session.read(1)

    async def system_config(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== System Configuration ===")
        await self.session.writeline()

        try:
            import toml
            from pathlib import Path

            config_path = Path("/home/dp/src/perestroikabbs/config.toml")
            if not config_path.exists():
                # Try alternate path
                config_path = Path("config.toml")

            if not config_path.exists():
                await self.session.writeline("Configuration file not found!")
                await self.session.writeline("Expected at: /home/dp/src/perestroikabbs/config.toml")
                await self.session.read(1)
                return

            # Load current config
            with open(config_path, 'r') as f:
                config = toml.load(f)

            # Display main settings
            await self.session.writeline("Current Configuration:")
            await self.session.writeline()

            if 'bbs' in config:
                bbs = config['bbs']
                await self.session.writeline("[BBS Settings]")
                await self.session.writeline(f"  Name: {bbs.get('name', 'Unknown')}")
                await self.session.writeline(f"  Host: {bbs.get('host', 'Unknown')}")
                await self.session.writeline(f"  Port: {bbs.get('port', 'Unknown')}")
                await self.session.writeline()

            if 'database' in config:
                db = config['database']
                await self.session.writeline("[Database]")
                db_url = db.get('url', '')
                # Mask password in URL
                if '@' in db_url:
                    parts = db_url.split('@')
                    if ':' in parts[0]:
                        proto_user = parts[0].rsplit(':', 1)[0]
                        masked_url = f"{proto_user}:****@{parts[1]}"
                    else:
                        masked_url = db_url
                else:
                    masked_url = db_url
                await self.session.writeline(f"  URL: {masked_url}")
                await self.session.writeline()

            if 'logging' in config:
                log = config['logging']
                await self.session.writeline("[Logging]")
                await self.session.writeline(f"  Level: {log.get('level', 'Unknown')}")
                await self.session.writeline(f"  File: {log.get('file', 'Unknown')}")
                await self.session.writeline()

            if 'files' in config:
                files = config['files']
                await self.session.writeline("[File Storage]")
                await self.session.writeline(f"  Base Path: {files.get('base_path', 'Unknown')}")
                await self.session.writeline(f"  Max Upload Size: {files.get('max_upload_size', 'Unknown')} bytes")
                await self.session.writeline()

            # Options menu
            await self.session.writeline("\nOptions:")
            await self.session.writeline("1. Change BBS name")
            await self.session.writeline("2. Change port")
            await self.session.writeline("3. Change log level")
            await self.session.writeline("4. View full config")
            await self.session.writeline("0. Back")

            choice = await self.session.readline("\r\nChoice: ")

            if choice == "1":
                new_name = await self.session.readline("New BBS name: ")
                if new_name:
                    config['bbs']['name'] = new_name
                    with open(config_path, 'w') as f:
                        toml.dump(config, f)
                    await self.session.writeline("\r\nBBS name updated. Restart required.")

            elif choice == "2":
                new_port = await self.session.readline("New port: ")
                try:
                    port = int(new_port)
                    if 1 <= port <= 65535:
                        config['bbs']['port'] = port
                        with open(config_path, 'w') as f:
                            toml.dump(config, f)
                        await self.session.writeline("\r\nPort updated. Restart required.")
                    else:
                        await self.session.writeline("\r\nInvalid port number.")
                except ValueError:
                    await self.session.writeline("\r\nInvalid port number.")

            elif choice == "3":
                await self.session.writeline("\r\nLog levels: DEBUG, INFO, WARNING, ERROR")
                new_level = await self.session.readline("New log level: ").upper()
                if new_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                    config['logging']['level'] = new_level
                    with open(config_path, 'w') as f:
                        toml.dump(config, f)
                    await self.session.writeline("\r\nLog level updated. Restart required.")
                else:
                    await self.session.writeline("\r\nInvalid log level.")

            elif choice == "4":
                await self.session.writeline("\r\n=== Full Configuration ===")
                with open(config_path, 'r') as f:
                    for line in f:
                        await self.session.writeline(line.rstrip())

        except Exception as e:
            await self.session.writeline(f"\r\nError accessing config: {e}")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def database_maintenance(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Database Maintenance ===")
        await self.session.writeline()

        await self.session.writeline("1. Vacuum database (optimize storage)")
        await self.session.writeline("2. Rebuild indexes")
        await self.session.writeline("3. Clean orphaned records")
        await self.session.writeline("4. Export backup")
        await self.session.writeline("5. Show database statistics")

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
            try:
                from ..storage.db import get_session
                from sqlalchemy import select, delete, or_
                from ..storage.models import Post, PrivateMessage, Transfer, ChatMessage, Board, User, File

                async with get_session() as db_session:
                    # Clean posts without valid board
                    orphan_posts = await db_session.execute(
                        select(Post).where(
                            ~Post.board_id.in_(select(Board.id))
                        )
                    )
                    orphan_count = len(orphan_posts.scalars().all())
                    if orphan_count > 0:
                        await db_session.execute(
                            delete(Post).where(
                                ~Post.board_id.in_(select(Board.id))
                            )
                        )
                        await self.session.writeline(f"  Removed {orphan_count} orphaned posts")

                    # Clean messages without valid sender or recipient
                    orphan_msgs = await db_session.execute(
                        select(PrivateMessage).where(
                            or_(
                                ~PrivateMessage.sender_id.in_(select(User.id)),
                                ~PrivateMessage.recipient_id.in_(select(User.id))
                            )
                        )
                    )
                    msg_count = len(orphan_msgs.scalars().all())
                    if msg_count > 0:
                        await db_session.execute(
                            delete(PrivateMessage).where(
                                or_(
                                    ~PrivateMessage.sender_id.in_(select(User.id)),
                                    ~PrivateMessage.recipient_id.in_(select(User.id))
                                )
                            )
                        )
                        await self.session.writeline(f"  Removed {msg_count} orphaned messages")

                    await db_session.commit()
                    await self.session.writeline("\r\nOrphaned records cleaned!")

            except Exception as e:
                await self.session.writeline(f"\r\nError cleaning orphans: {e}")

        elif choice == "4":
            await self.session.writeline("\r\nExporting backup...")
            try:
                import os
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"/var/lib/bbs/backups/bbs_backup_{timestamp}.sql"

                await self.session.writeline(f"  Creating backup: {backup_file}")
                await self.session.writeline("  (Would execute backup script here)")
                await self.session.writeline("\r\nBackup export would be created.")
            except Exception as e:
                await self.session.writeline(f"\r\nError creating backup: {e}")

        elif choice == "5":
            await self.session.writeline("\r\nDatabase Statistics:")
            try:
                from ..storage.db import get_session
                from sqlalchemy import text, func, select
                from ..storage.models import User, Board, Post, PrivateMessage, File, Transfer, ChatMessage, Session as SessionModel

                async with get_session() as db_session:
                    # Count records in each table
                    tables = {
                        'users': User,
                        'sessions': SessionModel,
                        'boards': Board,
                        'posts': Post,
                        'private_messages': PrivateMessage,
                        'files': File,
                        'transfers': Transfer,
                        'chat_messages': ChatMessage
                    }

                    for name, model in tables.items():
                        try:
                            count = await db_session.execute(select(func.count()).select_from(model))
                            await self.session.writeline(f"  {name:20} {count.scalar():8} records")
                        except Exception:
                            pass

                    # Database size (MySQL/MariaDB specific)
                    try:
                        db_url = str(db_session.bind.url)
                        if 'mysql' in db_url or 'mariadb' in db_url:
                            result = await db_session.execute(
                                text("SELECT SUM(data_length + index_length) / 1024 / 1024 AS size_mb "
                                     "FROM information_schema.tables "
                                     "WHERE table_schema = DATABASE()")
                            )
                            size = result.scalar() or 0
                            await self.session.writeline(f"\n  Total database size: {size:.2f} MB")
                    except Exception:
                        pass

            except Exception as e:
                await self.session.writeline(f"\r\nError getting stats: {e}")

        await self.session.read(1)