import asyncio
from typing import Optional

from ..encoding import CharsetManager
from ..session import Session
from ..storage.repositories import UserRepository
from ..security.auth import AuthManager
from ..utils.logger import get_logger

logger = get_logger("ui.login")


class LoginUI:
    def __init__(self, session: Session, charset_manager: CharsetManager):
        self.session = session
        self.charset_manager = charset_manager
        self.auth_manager = AuthManager()
        self.user_repo = UserRepository()
        self.max_attempts = 3

    async def run(self) -> bool:
        await self.select_encoding()

        await self.session.writeline()
        await self.session.writeline("Please log in or register for a new account.")
        await self.session.writeline()

        options = [
            ("L", "Login with existing account"),
            ("N", "New user registration"),
            ("G", "Guest login"),
            ("Q", "Quit"),
        ]

        choice = await self.session.menu_select(options, "\r\nYour choice: ")

        if choice == "L":
            return await self.login()
        elif choice == "N":
            return await self.register()
        elif choice == "G":
            return await self.guest_login()
        else:
            return False

    async def select_encoding(self) -> None:
        await self.session.writeline("\r\nSelect your terminal encoding:")
        await self.session.writeline()

        encodings = self.charset_manager.get_encoding_menu()
        for i, (display, _) in enumerate(encodings, 1):
            await self.session.writeline(f"  [{i}] {display}")

        await self.session.writeline(f"  [0] Auto-detect")
        await self.session.writeline(f"  [7] 7-bit ASCII only (legacy terminals)")
        await self.session.writeline()

        while True:
            choice = await self.session.readline("Selection (0-" + str(len(encodings)) + ", 7 for 7-bit): ")

            try:
                idx = int(choice)
                if idx == 0:
                    test_string = "Testing: ╔═╗ █▓▒░ ♠♥♦♣"
                    await self.session.write(f"\r\n{test_string}\r\n")
                    await self.session.writeline("Do you see the special characters correctly?")
                    confirm = await self.session.readline("(Y/N): ")

                    if confirm.upper() == "Y":
                        break
                    else:
                        await self.session.writeline("Please select your encoding manually.")
                        continue

                elif idx == 7:
                    # 7-bit ASCII mode
                    self.session.capabilities.seven_bit = True
                    self.session.capabilities.ansi = False
                    self.session.capabilities.color = False
                    self.session.set_encoding("ascii")
                    await self.session.writeline("7-bit ASCII mode enabled")
                    break
                elif 1 <= idx <= len(encodings):
                    encoding = encodings[idx - 1][1]
                    self.session.set_encoding(encoding)
                    await self.session.writeline(f"Encoding set to {encodings[idx - 1][0]}")
                    break
                else:
                    await self.session.writeline("Invalid selection.")

            except ValueError:
                await self.session.writeline("Please enter a number.")

    async def login(self) -> bool:
        for attempt in range(self.max_attempts):
            await self.session.writeline()
            username = await self.session.readline("Username: ")

            if not username:
                continue

            password = await self.session.read_password("Password: ")

            user = await self.user_repo.get_by_username(username)

            if user and await self.auth_manager.verify_password(password, user.password_hash):
                self.session.user_id = user.id
                self.session.username = user.username
                self.session.access_level = user.access_level

                await self.user_repo.update_last_login(user.id)
                logger.info(f"User {username} logged in (Session: {self.session.id})")
                return True

            else:
                await self.session.writeline("\r\nInvalid username or password.")
                if attempt < self.max_attempts - 1:
                    await self.session.writeline(f"Attempts remaining: {self.max_attempts - attempt - 1}")
                await asyncio.sleep(1)

        await self.session.writeline("\r\nToo many failed attempts.")
        return False

    async def register(self) -> bool:
        await self.session.writeline()
        await self.session.writeline("=== New User Registration ===")
        await self.session.writeline()

        while True:
            username = await self.session.readline("Choose a username (3-20 chars): ")

            if len(username) < 3:
                await self.session.writeline("Username too short.")
                continue

            if len(username) > 20:
                await self.session.writeline("Username too long.")
                continue

            if await self.user_repo.get_by_username(username):
                await self.session.writeline("Username already taken.")
                continue

            break

        while True:
            password = await self.session.read_password("Choose a password (min 8 chars): ")

            if len(password) < 8:
                await self.session.writeline("\r\nPassword too short.")
                continue

            confirm = await self.session.read_password("Confirm password: ")

            if password != confirm:
                await self.session.writeline("\r\nPasswords don't match.")
                continue

            break

        await self.session.writeline()
        email = await self.session.readline("Email (optional): ")
        real_name = await self.session.readline("Real name (optional): ")
        location = await self.session.readline("Location (optional): ")

        password_hash = await self.auth_manager.hash_password(password)

        user = await self.user_repo.create(
            username=username,
            password_hash=password_hash,
            email=email or None,
            real_name=real_name or None,
            location=location or None,
        )

        if user:
            self.session.user_id = user.id
            self.session.username = user.username
            self.session.access_level = user.access_level

            await self.session.writeline()
            await self.session.writeline(f"Registration successful! Welcome, {username}!")
            logger.info(f"New user registered: {username} (Session: {self.session.id})")
            return True

        else:
            await self.session.writeline("\r\nRegistration failed. Please try again.")
            return False

    async def guest_login(self) -> bool:
        self.session.username = "Guest"
        self.session.access_level = 0
        await self.session.writeline("\r\nLogged in as Guest (limited access)")
        logger.info(f"Guest login (Session: {self.session.id})")
        return True