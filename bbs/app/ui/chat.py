"""
Chat room UI module.

Provides real-time chat functionality with database persistence.
"""

from typing import Dict, List, Optional, Set

from ..session import Session
from ..storage.container import RepositoryContainer, get_repos
from ..utils.logger import get_logger
from .base import UIModule
from .components.menu_builder import MenuBuilder

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
        # Broadcast join message in each participant's language
        for participant in self.participants:
            if participant != session:
                msg = f"*** {participant.t('chat.user_joined', user=session.username)}"
                try:
                    await participant.writeline(f"\r{msg}")
                except Exception:
                    pass

    async def remove_participant(self, session: Session) -> None:
        """Remove a participant from the room."""
        if session in self.participants:
            self.participants.remove(session)
            # Broadcast leave message in each participant's language
            for participant in self.participants:
                msg = f"*** {participant.t('chat.user_left', user=session.username)}"
                try:
                    await participant.writeline(f"\r{msg}")
                except Exception:
                    pass

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


class ChatUI(UIModule[None]):
    """Chat room user interface."""

    def __init__(
        self,
        session: Session,
        repos: Optional[RepositoryContainer] = None,
    ):
        super().__init__(session, repos)
        self.chat_manager = ChatManager()

    async def run(self) -> None:
        """Main chat menu."""
        if not await self.check_access():
            return

        menu = (
            MenuBuilder(self.session, self.session.t('chat.title').strip('= '))
            .option("1", self.session.t('chat.main_lobby'), lambda: self._join_room("main"))
            .option("2", self.session.t('chat.tech_talk'), lambda: self._join_room("tech"))
            .option("3", self.session.t('chat.random'), lambda: self._join_room("random"))
            .separator()
            .option("L", self.session.t('chat.room_list'), self._list_rooms)
            .back("Q", self.session.t('common.back'))
        )

        await menu.run()

    async def _list_rooms(self) -> None:
        """List all active chat rooms."""
        await self.clear_and_header(self.session.t('chat.active_rooms'))

        rooms = self.chat_manager.rooms
        if not rooms:
            await self.session.writeline(self.session.t('chat.no_active_rooms'))
        else:
            for room_name, room in rooms.items():
                user_count = len(room.participants)
                await self.session.writeline(f"  {room_name}: {self.session.t('chat.users_count', count=user_count)}")

        await self.pause()

    async def _join_room(self, room_name: str) -> None:
        """Join a chat room."""
        room = await self.chat_manager.get_or_create_room(room_name)

        await self.clear_and_header(self.session.t('chat.room_header', room=room_name))
        await self.session.writeline(self.session.t('chat.type_help'))
        await self.session.writeline("-" * 50)

        # Load history from database
        history = await self.chat_manager.get_room_history(room_name, limit=10)
        for msg, _ in history:
            await self.session.writeline(msg)

        await room.add_participant(self.session)

        try:
            await self._chat_loop(room)
        finally:
            await room.remove_participant(self.session)

    async def _chat_loop(self, room: ChatRoom) -> None:
        """Main chat input loop."""
        await self.session.writeline()
        await self.session.writeline(self.session.t('chat.now_chatting'))
        await self.session.writeline()

        while True:
            message = await self.session.readline(f"[{self.session.username}]: ")

            if not message:
                continue

            if message.startswith("/"):
                if not await self._handle_command(message, room):
                    break
            else:
                await room.broadcast(message, self.session)

    async def _handle_command(self, command: str, room: ChatRoom) -> bool:
        """
        Handle chat commands.

        Returns:
            True to continue chat loop, False to exit
        """
        cmd_parts = command.split()
        cmd = cmd_parts[0].lower()

        if cmd in ("/quit", "/exit"):
            await self.session.writeline(self.session.t('chat.leaving'))
            return False

        elif cmd == "/help":
            await self.session.writeline(f"\r\n=== {self.session.t('chat.commands_title')} ===")
            await self.session.writeline(f"  {self.session.t('chat.cmd_quit')}")
            await self.session.writeline(f"  {self.session.t('chat.cmd_who')}")
            await self.session.writeline(f"  {self.session.t('chat.cmd_me')}")
            await self.session.writeline(f"  {self.session.t('chat.cmd_whisper')}")
            await self.session.writeline(f"  {self.session.t('chat.cmd_clear')}")
            await self.session.writeline()

        elif cmd == "/who":
            await self.session.writeline(f"\r\n{self.session.t('chat.users_in_room')}")
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
                    # Use recipient's language for their message
                    await participant.writeline(
                        f"\r{participant.t('chat.whisper_from', user=self.session.username)}: {whisper_msg}"
                    )
                    await self.session.writeline(f"{self.session.t('chat.whisper_sent', user=target_username)}: {whisper_msg}")
                    break
            else:
                await self.session.writeline(self.session.t('chat.user_not_found', user=target_username))

        elif cmd == "/clear":
            await self.session.clear_screen()
            await self.session.writeline(f"=== {self.session.t('chat.room_header', room=room.name)} ===")
            await self.session.writeline("-" * 50)

        else:
            await self.session.writeline(self.session.t('chat.unknown_cmd', cmd=cmd))

        return True
