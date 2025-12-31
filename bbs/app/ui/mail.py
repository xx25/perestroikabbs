from datetime import datetime
from typing import List, Optional

from ..session import Session
from ..storage.models import PrivateMessage
from ..storage.repositories import MailRepository, UserRepository
from ..utils.logger import get_logger
from .menu import Menu

logger = get_logger("ui.mail")


class MailUI:
    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository()
        self.mail_repo = MailRepository()

    async def run(self) -> None:
        menu = Menu(self.session, self.session.t('mail.title').strip('= '))

        menu.add_item("I", self.session.t('mail.inbox'), self.inbox)
        menu.add_item("S", self.session.t('mail.sent'), self.sent)
        menu.add_item("C", self.session.t('mail.compose'), self.compose)
        menu.add_item("Q", self.session.t('common.back'), lambda: setattr(menu, "running", False))

        await menu.run()

    async def inbox(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Inbox ===")
        await self.session.writeline()

        if not self.session.user_id:
            await self.session.writeline("You must be logged in to view mail.")
            await self.session.read(1)
            return

        # Get messages for current user
        messages = await self.mail_repo.get_inbox(self.session.user_id)

        if not messages:
            await self.session.writeline("No messages in inbox.")
        else:
            await self.session.writeline(f"{'#':<4} {'From':<15} {'Subject':<30} {'Date':<20} {'Read':<5}")
            await self.session.writeline("-" * 75)

            for i, msg in enumerate(messages, 1):
                sender = await self.user_repo.get_by_id(msg.sender_id)
                sender_name = sender.username if sender else "Unknown"
                date_str = msg.created_at.strftime("%Y-%m-%d %H:%M")
                read_status = "Yes" if msg.read_at else "No"

                await self.session.writeline(
                    f"{i:<4} {sender_name:<15} {msg.subject[:29]:<30} {date_str:<20} {read_status:<5}"
                )

        await self.session.writeline()
        await self.session.writeline("Commands: [R]ead, [D]elete, [Q]uit")

        choice = await self.session.readline(f"{self.session.t('login.your_choice')}: ")

        if choice.upper() == "R" and messages:
            await self.read_message(messages)
        elif choice.upper() == "D" and messages:
            await self.delete_message(messages)

    async def sent(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Sent Mail ===")
        await self.session.writeline()

        if not self.session.user_id:
            await self.session.writeline("You must be logged in to view mail.")
            await self.session.read(1)
            return

        # Get sent messages
        messages = await self.mail_repo.get_sent(self.session.user_id)

        if not messages:
            await self.session.writeline("No sent messages.")
        else:
            await self.session.writeline(f"{'#':<4} {'To':<15} {'Subject':<30} {'Date':<20}")
            await self.session.writeline("-" * 70)

            for i, msg in enumerate(messages, 1):
                recipient = await self.user_repo.get_by_id(msg.recipient_id)
                recipient_name = recipient.username if recipient else "Unknown"
                date_str = msg.created_at.strftime("%Y-%m-%d %H:%M")

                await self.session.writeline(
                    f"{i:<4} {recipient_name:<15} {msg.subject[:29]:<30} {date_str:<20}"
                )

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def compose(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Compose Message ===")
        await self.session.writeline()

        if not self.session.user_id:
            await self.session.writeline("You must be logged in to send mail.")
            await self.session.read(1)
            return

        recipient = await self.session.readline("To (username): ")
        if not recipient:
            await self.session.writeline("Message cancelled.")
            return

        user = await self.user_repo.get_by_username(recipient)
        if not user:
            await self.session.writeline(f"User '{recipient}' not found.")
            await self.session.writeline("\r\nPress any key to continue...")
            await self.session.read(1)
            return

        subject = await self.session.readline("Subject: ")
        if not subject:
            await self.session.writeline("Message cancelled.")
            return

        await self.session.writeline("Enter message body (end with '.' on a line by itself):")
        body_lines = []
        while True:
            line = await self.session.readline()
            if line == ".":
                break
            body_lines.append(line)

        body = "\n".join(body_lines)

        if body:
            # Send the message
            message = await self.mail_repo.send_message(
                sender_id=self.session.user_id,
                recipient_id=user.id,
                subject=subject,
                body=body
            )

            if message:
                await self.session.writeline("\r\nMessage sent successfully!")
            else:
                await self.session.writeline("\r\nError sending message.")
        else:
            await self.session.writeline("\r\nMessage cancelled.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def read_message(self, messages: List[PrivateMessage]) -> None:
        """Read a specific message"""
        await self.session.writeline()
        msg_num = await self.session.readline("Message number to read: ")

        try:
            idx = int(msg_num) - 1
            if 0 <= idx < len(messages):
                msg = messages[idx]

                await self.session.clear_screen()
                await self.session.writeline("=== Message ===")
                await self.session.writeline()

                sender = await self.user_repo.get_by_id(msg.sender_id)
                sender_name = sender.username if sender else "Unknown"

                await self.session.writeline(f"From: {sender_name}")
                await self.session.writeline(f"Date: {msg.created_at.strftime('%Y-%m-%d %H:%M')}")
                await self.session.writeline(f"Subject: {msg.subject}")
                await self.session.writeline("-" * 50)
                await self.session.writeline()
                await self.session.writeline(msg.body)
                await self.session.writeline()

                # Mark as read
                if not msg.read_at:
                    await self.mail_repo.mark_as_read(msg.id)

                await self.session.writeline("-" * 50)
                await self.session.writeline("Commands: [R]eply, [D]elete, [Q]uit")

                choice = await self.session.readline(f"{self.session.t('login.your_choice')}: ")

                if choice.upper() == "R":
                    await self.reply_message(msg, sender_name)
                elif choice.upper() == "D":
                    await self.mail_repo.delete_message(msg.id, self.session.user_id)
                    await self.session.writeline("\r\nMessage deleted.")
                    await self.session.read(1)

        except (ValueError, IndexError):
            await self.session.writeline("Invalid message number.")
            await self.session.read(1)

    async def delete_message(self, messages: List[PrivateMessage]) -> None:
        """Delete a message"""
        await self.session.writeline()
        msg_num = await self.session.readline("Message number to delete: ")

        try:
            idx = int(msg_num) - 1
            if 0 <= idx < len(messages):
                msg = messages[idx]
                await self.mail_repo.delete_message(msg.id, self.session.user_id)
                await self.session.writeline("\r\nMessage deleted.")

        except (ValueError, IndexError):
            await self.session.writeline("Invalid message number.")

        await self.session.read(1)

    async def reply_message(self, original_msg: PrivateMessage, sender_name: str) -> None:
        """Reply to a message"""
        await self.session.writeline()
        await self.session.writeline("=== Reply ===")

        subject = f"Re: {original_msg.subject}"
        await self.session.writeline(f"Subject: {subject}")

        await self.session.writeline("Enter reply (end with '.' on a line by itself):")
        body_lines = []
        while True:
            line = await self.session.readline()
            if line == ".":
                break
            body_lines.append(line)

        body = "\n".join(body_lines)

        if body:
            # Add quoted original message
            quoted = f"\n\n--- Original Message ---\nFrom: {sender_name}\nDate: {original_msg.created_at}\n\n{original_msg.body}"
            body = body + quoted

            message = await self.mail_repo.send_message(
                sender_id=self.session.user_id,
                recipient_id=original_msg.sender_id,
                subject=subject,
                body=body
            )

            if message:
                await self.session.writeline("\r\nReply sent successfully!")
            else:
                await self.session.writeline("\r\nError sending reply.")
        else:
            await self.session.writeline("\r\nReply cancelled.")

        await self.session.read(1)