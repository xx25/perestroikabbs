from typing import Optional

from ..session import Session
from ..storage.repositories import BoardRepository, UserRepository
from ..utils.logger import get_logger
from .menu import Menu

logger = get_logger("ui.boards")


class BoardsUI:
    def __init__(self, session: Session):
        self.session = session
        self.board_repo = BoardRepository()
        self.user_repo = UserRepository()

    async def run(self) -> None:
        menu = Menu(self.session, "Message Boards")

        boards = await self.board_repo.get_all_boards(self.session.access_level)

        for board in boards:
            menu.add_item(
                str(board.id),
                f"{board.name} ({board.post_count} posts)",
                lambda b=board: self.view_board(b),
            )

        menu.add_item("N", "New Post", self.new_post)
        menu.add_item("S", "Search", self.search_posts)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))

        await menu.run()

    async def view_board(self, board) -> None:
        await self.session.clear_screen()
        await self.session.writeline(f"=== {board.name} ===")
        if board.description:
            await self.session.writeline(board.description)
        await self.session.writeline()

        posts = await self.board_repo.get_posts(board.id, limit=20)

        if not posts:
            await self.session.writeline("No posts in this board yet.")
        else:
            for i, post in enumerate(posts, 1):
                author = await self.user_repo.get_by_id(post.author_id)
                author_name = author.username if author else "Unknown"
                date_str = post.created_at.strftime("%Y-%m-%d %H:%M")

                await self.session.writeline(f"[{i}] {post.subject}")
                await self.session.writeline(f"    By: {author_name} | Date: {date_str}")
                await self.session.writeline()

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def new_post(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== New Post ===")
        await self.session.writeline()

        boards = await self.board_repo.get_all_boards(self.session.access_level)

        if not boards:
            await self.session.writeline("No boards available.")
            await self.session.read(1)
            return

        await self.session.writeline("Select board:")
        for i, board in enumerate(boards, 1):
            await self.session.writeline(f"  [{i}] {board.name}")

        board_choice = await self.session.readline("\r\nBoard number: ")

        try:
            board_idx = int(board_choice) - 1
            if 0 <= board_idx < len(boards):
                board = boards[board_idx]

                subject = await self.session.readline("Subject: ")
                if not subject:
                    await self.session.writeline("Post cancelled.")
                    return

                await self.session.writeline("Enter message body (end with '.' on a line by itself):")
                body_lines = []
                while True:
                    line = await self.session.readline()
                    if line == ".":
                        break
                    body_lines.append(line)

                body = "\n".join(body_lines)

                if body and self.session.user_id:
                    await self.board_repo.create_post(
                        board_id=board.id,
                        author_id=self.session.user_id,
                        subject=subject,
                        body=body,
                    )
                    await self.session.writeline("\r\nPost created successfully!")
                else:
                    await self.session.writeline("\r\nPost cancelled.")
        except (ValueError, IndexError):
            await self.session.writeline("Invalid selection.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def search_posts(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Search Posts ===")
        await self.session.writeline()

        query = await self.session.readline("Search for: ")

        if query:
            # Search posts
            posts = await self.board_repo.search_posts(query, self.session.access_level)

            if posts:
                await self.session.writeline(f"\r\nFound {len(posts)} post(s):")
                await self.session.writeline()

                for post in posts[:20]:  # Limit to first 20 results
                    board = await self.board_repo.get_board(post.board_id)
                    board_name = board.name if board else "Unknown"
                    author = await self.user_repo.get_by_id(post.author_id)
                    author_name = author.username if author else "Unknown"
                    date_str = post.created_at.strftime("%Y-%m-%d")

                    await self.session.writeline(f"Board: {board_name}")
                    await self.session.writeline(f"Subject: {post.subject}")
                    await self.session.writeline(f"Author: {author_name} | Date: {date_str}")
                    await self.session.writeline(f"Preview: {post.body[:100]}...")
                    await self.session.writeline("-" * 40)

            else:
                await self.session.writeline("\r\nNo posts found matching your search.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)