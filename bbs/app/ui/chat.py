import asyncio
from typing import Dict, List, Optional, Set

from ..session import Session
from ..storage.container import get_repos
from ..utils.logger import get_logger
from .menu import Menu

logger = get_logger("ui.chat")


class ChatManager:
    """
    Manages active chat rooms with database persistence.

    Rooms are created/loaded from database on first access.
    Participants are tracked in-memory for real-time messaging.
    Messages are persisted to database.
    """

    _instance: Optional["ChatManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rooms: Dict[str, "ChatRoom"] = {}
            cls._instance.repos = get_repos()
        return cls._instance

    async def get_or_create_room(self, room_name: str) -> "ChatRoom":
        """
        Get an existing room or create a new one.

        Checks in-memory cache first, then database.
        Creates in database if not found.
        """
        if room_name not in self.rooms:
            # Check if room exists in database
            db_room = await self.repos.chat.get_room_by_name(room_name)

            if not db_room:
                # Create in database
                db_room = await self.repos.chat.create_room(
                    name=room_name,
                    description=f"Chat room: {room_name}"
                )
                logger.info(f"Created new chat room in database: {room_name}")

            # Create in-memory room with database ID
            self.rooms[room_name] = ChatRoom(
                name=room_name,
                db_room_id=db_room.id if db_room else None
            )

        return self.rooms[room_name]

    async def get_room_history(self, room_name: str, limit: int = 50) -> List[tuple]:
        """Load room history from database."""
        db_room = await self.repos.chat.get_room_by_name(room_name)
        if not db_room:
            return []

        messages = await self.repos.chat.get_recent_messages(db_room.id, limit)
        history = []
        for msg in messages:
            # Get author username
            author = await self.repos.users.get_by_id(msg.author_id)
            author_name = author.username if author else "Unknown"
            formatted = f"<{author_name}> {msg.body}"
            history.append((formatted, str(msg.created_at)))
        return history


class ChatRoom:
    """
    A chat room with real-time participants and database persistence.

    Participants are tracked in-memory for real-time messaging.
    Messages are persisted to the database for history.
    """

    def __init__(self, name: str, db_room_id: Optional[int] = None):
        self.name = name
        self.db_room_id = db_room_id
        self.participants: Set[Session] = set()
        self.repos = get_repos()

    async def add_participant(self, session: Session) -> None:
        """Add a participant to the room."""
        self.participants.add(session)
        await self.broadcast(f"*** {session.username} has entered the room", None)

    async def remove_participant(self, session: Session) -> None:
        """Remove a participant from the room."""
        if session in self.participants:
            self.participants.remove(session)
            await self.broadcast(f"*** {session.username} has left the room", None)

    async def broadcast(
        self, message: str, sender: Optional[Session], persist: bool = True
    ) -> None:
        """
        Broadcast a message to all participants.

        Args:
            message: Message text
            sender: Sending session (None for system messages)
            persist: Whether to persist to database
        """
        if sender:
            formatted = f"<{sender.username}> {message}"
            # Persist user messages to database
            if persist and self.db_room_id and sender.user_id:
                try:
                    await self.repos.chat.save_message(
                        room_id=self.db_room_id,
                        author_id=sender.user_id,
                        body=message
                    )
                except Exception as e:
                    logger.error(f"Failed to persist chat message: {e}")
        else:
            formatted = message

        # Broadcast to active participants
        for participant in self.participants:
            if participant != sender or sender is None:
                try:
                    await participant.writeline(f"\r{formatted}")
                except Exception as e:
                    logger.error(f"Failed to send message to {participant.username}: {e}")


class ChatUI:
    """Chat room user interface."""

    def __init__(self, session: Session):
        self.session = session
        self.repos = get_repos()
        self.chat_manager = ChatManager()

    async def run(self) -> None:
        """Main chat menu."""
        menu = Menu(self.session, "Chat Rooms")

        menu.add_item("1", "Main Lobby", lambda: self.join_room("main"))
        menu.add_item("2", "Tech Talk", lambda: self.join_room("tech"))
        menu.add_item("3", "Random", lambda: self.join_room("random"))
        menu.add_item("L", "List Active Rooms", self.list_rooms)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))

        await menu.run()

    async def list_rooms(self) -> None:
        """List all active chat rooms."""
        await self.session.clear_screen()
        await self.session.writeline("=== Active Chat Rooms ===")
        await self.session.writeline()

        # Show in-memory active rooms with participant counts
        rooms = self.chat_manager.rooms
        if not rooms:
            await self.session.writeline("No active chat rooms.")
        else:
            for room_name, room in rooms.items():
                user_count = len(room.participants)
                await self.session.writeline(f"  {room_name}: {user_count} user(s)")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def join_room(self, room_name: str) -> None:
        """Join a chat room."""
        # Get or create room (async - may create in database)
        room = await self.chat_manager.get_or_create_room(room_name)

        await self.session.clear_screen()
        await self.session.writeline(f"=== Chat Room: {room_name} ===")
        await self.session.writeline("Type /help for commands, /quit to exit")
        await self.session.writeline("-" * 50)

        # Load history from database
        history = await self.chat_manager.get_room_history(room_name, limit=10)
        for msg, _ in history:
            await self.session.writeline(msg)

        await room.add_participant(self.session)

        try:
            await self.chat_loop(room)
        finally:
            await room.remove_participant(self.session)

    async def chat_loop(self, room: ChatRoom) -> None:
        await self.session.writeline()
        await self.session.writeline("You are now in the chat room. Start typing!")
        await self.session.writeline()

        while True:
            message = await self.session.readline(f"[{self.session.username}]: ")

            if not message:
                continue

            if message.startswith("/"):
                if not await self.handle_command(message, room):
                    break
            else:
                await room.broadcast(message, self.session)

    async def handle_command(self, command: str, room: ChatRoom) -> bool:
        cmd_parts = command.split()
        cmd = cmd_parts[0].lower()

        if cmd == "/quit" or cmd == "/exit":
            await self.session.writeline("Leaving chat room...")
            return False

        elif cmd == "/help":
            await self.session.writeline("\r\n=== Chat Commands ===")
            await self.session.writeline("  /quit, /exit - Leave the chat room")
            await self.session.writeline("  /who - List users in room")
            await self.session.writeline("  /me <action> - Perform an action")
            await self.session.writeline("  /whisper <user> <msg> - Private message")
            await self.session.writeline("  /clear - Clear screen")
            await self.session.writeline()

        elif cmd == "/who":
            await self.session.writeline("\r\nUsers in room:")
            for participant in room.participants:
                await self.session.writeline(f"  - {participant.username}")
            await self.session.writeline()

        elif cmd == "/me" and len(cmd_parts) > 1:
            action = " ".join(cmd_parts[1:])
            await room.broadcast(f"* {self.session.username} {action}", None)

        elif cmd == "/whisper" and len(cmd_parts) > 2:
            target_username = cmd_parts[1]
            whisper_msg = " ".join(cmd_parts[2:])

            for participant in room.participants:
                if participant.username == target_username:
                    await participant.writeline(f"\r[Whisper from {self.session.username}]: {whisper_msg}")
                    await self.session.writeline(f"[Whisper to {target_username}]: {whisper_msg}")
                    break
            else:
                await self.session.writeline(f"User '{target_username}' not found in room.")

        elif cmd == "/clear":
            await self.session.clear_screen()
            await self.session.writeline(f"=== Chat Room: {room.name} ===")
            await self.session.writeline("-" * 50)

        else:
            await self.session.writeline(f"Unknown command: {cmd}")

        return True