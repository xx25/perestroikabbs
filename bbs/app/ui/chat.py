import asyncio
from typing import Dict, List, Optional, Set

from ..session import Session
from ..storage.repositories import ChatRepository, UserRepository
from ..utils.logger import get_logger
from .menu import Menu

logger = get_logger("ui.chat")


class ChatManager:
    _instance: Optional["ChatManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rooms = {}
        return cls._instance

    def get_or_create_room(self, room_name: str) -> "ChatRoom":
        if room_name not in self.rooms:
            self.rooms[room_name] = ChatRoom(room_name)
        return self.rooms[room_name]


class ChatRoom:
    def __init__(self, name: str):
        self.name = name
        self.participants: Set[Session] = set()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.history: List[tuple[str, str]] = []

    async def add_participant(self, session: Session) -> None:
        self.participants.add(session)
        await self.broadcast(f"*** {session.username} has entered the room", None)

    async def remove_participant(self, session: Session) -> None:
        if session in self.participants:
            self.participants.remove(session)
            await self.broadcast(f"*** {session.username} has left the room", None)

    async def broadcast(self, message: str, sender: Optional[Session]) -> None:
        timestamp = asyncio.get_event_loop().time()

        if sender:
            formatted = f"<{sender.username}> {message}"
        else:
            formatted = message

        self.history.append((formatted, str(timestamp)))
        if len(self.history) > 100:
            self.history.pop(0)

        for participant in self.participants:
            if participant != sender or sender is None:
                try:
                    await participant.writeline(f"\r{formatted}")
                except Exception as e:
                    logger.error(f"Failed to send message to {participant.username}: {e}")


class ChatUI:
    def __init__(self, session: Session):
        self.session = session
        self.chat_repo = ChatRepository()
        self.user_repo = UserRepository()
        self.chat_manager = ChatManager()

    async def run(self) -> None:
        menu = Menu(self.session, "Chat Rooms")

        menu.add_item("1", "Main Lobby", lambda: self.join_room("main"))
        menu.add_item("2", "Tech Talk", lambda: self.join_room("tech"))
        menu.add_item("3", "Random", lambda: self.join_room("random"))
        menu.add_item("L", "List Active Rooms", self.list_rooms)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))

        await menu.run()

    async def list_rooms(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Active Chat Rooms ===")
        await self.session.writeline()

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
        room = self.chat_manager.get_or_create_room(room_name)

        await self.session.clear_screen()
        await self.session.writeline(f"=== Chat Room: {room_name} ===")
        await self.session.writeline("Type /help for commands, /quit to exit")
        await self.session.writeline("-" * 50)

        for msg, _ in room.history[-10:]:
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