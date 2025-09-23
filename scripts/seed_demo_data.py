#!/usr/bin/env python3

"""
Seed the database with demo data for testing and development
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bbs.app.storage.db import init_database, create_tables
from bbs.app.storage.models import UserStatus
from bbs.app.storage.repositories import BoardRepository, ChatRepository, UserRepository
from bbs.app.security.auth import AuthManager
from bbs.app.utils.logger import setup_logging

logger = setup_logging()


async def seed_data():
    """Seed the database with demo data"""
    logger.info("Initializing database...")
    await init_database()
    await create_tables()

    auth = AuthManager()
    user_repo = UserRepository()
    board_repo = BoardRepository()
    chat_repo = ChatRepository()

    # Create demo users
    logger.info("Creating demo users...")

    users = [
        ("sysop", "admin123", "sysop@bbs.local", 100, "System Operator"),
        ("john", "password", "john@example.com", 1, "John Doe"),
        ("jane", "password", "jane@example.com", 5, "Jane Smith"),
        ("moderator", "modpass", "mod@bbs.local", 10, "Moderator"),
        ("guest", "guest", None, 0, "Guest User"),
    ]

    created_users = {}
    for username, password, email, access_level, real_name in users:
        existing = await user_repo.get_by_username(username)
        if not existing:
            password_hash = await auth.hash_password(password)
            user = await user_repo.create(
                username=username,
                password_hash=password_hash,
                email=email,
                real_name=real_name,
            )
            if user:
                await user_repo.update_access_level(user.id, access_level)
                created_users[username] = user
                logger.info(f"  Created user: {username} (access: {access_level})")
        else:
            created_users[username] = existing
            logger.info(f"  User exists: {username}")

    # Create demo boards
    logger.info("Creating demo boards...")

    boards_data = [
        ("general", "General Discussion", 0, 1),
        ("tech", "Technology & Computing", 0, 1),
        ("games", "Gaming Discussion", 0, 1),
        ("marketplace", "Buy, Sell, Trade", 1, 1),
        ("admin", "Administration", 10, 10),
    ]

    created_boards = {}
    for name, description, min_read, min_write in boards_data:
        existing = await board_repo.get_board_by_name(name)
        if not existing:
            board = await board_repo.create_board(
                name=name,
                description=description,
                min_read=min_read,
                min_write=min_write,
            )
            created_boards[name] = board
            logger.info(f"  Created board: {name}")
        else:
            created_boards[name] = existing
            logger.info(f"  Board exists: {name}")

    # Create demo posts
    logger.info("Creating demo posts...")

    if created_boards and created_users:
        posts_data = [
            ("general", "sysop", "Welcome to Perestroika BBS!", "Welcome everyone to our new BBS system!"),
            ("general", "john", "Hello World", "Just saying hi to everyone!"),
            ("tech", "jane", "Python vs Ruby", "What do you think is better for web development?"),
            ("games", "john", "Favorite retro games?", "What are your favorite games from the 80s and 90s?"),
        ]

        for board_name, author_name, subject, body in posts_data:
            board = created_boards.get(board_name)
            user = created_users.get(author_name)

            if board and user:
                post = await board_repo.create_post(
                    board_id=board.id,
                    author_id=user.id,
                    subject=subject,
                    body=body,
                )
                logger.info(f"  Created post: '{subject}' in {board_name}")

    # Create chat rooms
    logger.info("Creating chat rooms...")

    rooms_data = [
        ("main", "Main Lobby", 0, False),
        ("tech", "Tech Talk", 0, False),
        ("random", "Random Chat", 0, False),
        ("moderators", "Moderator Room", 10, True),
    ]

    for name, description, min_access, is_private in rooms_data:
        existing = await chat_repo.get_room_by_name(name)
        if not existing:
            room = await chat_repo.create_room(
                name=name,
                description=description,
                min_access=min_access,
                is_private=is_private,
            )
            logger.info(f"  Created chat room: {name}")
        else:
            logger.info(f"  Chat room exists: {name}")

    logger.info("Demo data seeding completed!")
    logger.info("")
    logger.info("Demo user credentials:")
    logger.info("  sysop / admin123  (Sysop)")
    logger.info("  john / password   (Normal user)")
    logger.info("  jane / password   (Trusted user)")
    logger.info("  moderator / modpass (Moderator)")
    logger.info("  guest / guest     (Guest)")


async def main():
    try:
        await seed_data()
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())