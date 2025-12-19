from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import (
    Board, ChatMessage, ChatRoom, File, FileArea, Post, PrivateMessage,
    Session as SessionModel, Transfer, User, UserStatus
)
from ..utils.logger import get_logger

logger = get_logger("storage.repositories")


class UserRepository:
    async def create(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        real_name: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Optional[User]:
        try:
            async with get_session() as session:
                user = User(
                    username=username,
                    password_hash=password_hash,
                    email=email,
                    real_name=real_name,
                    location=location,
                    created_at=datetime.utcnow(),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    async def get_by_id(self, user_id: int) -> Optional[User]:
        async with get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()

    async def update_last_login(self, user_id: int) -> None:
        async with get_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    last_login_at=datetime.utcnow(),
                    login_count=User.login_count + 1,
                )
            )
            await session.commit()

    async def get_active_users(self, limit: int = 50) -> List[User]:
        async with get_session() as session:
            result = await session.execute(
                select(User)
                .where(User.status == UserStatus.ACTIVE)
                .order_by(User.last_login_at.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def search_users(self, query: str) -> List[User]:
        async with get_session() as session:
            result = await session.execute(
                select(User)
                .where(
                    and_(
                        User.status == UserStatus.ACTIVE,
                        or_(
                            User.username.ilike(f"%{query}%"),
                            User.real_name.ilike(f"%{query}%"),
                        ),
                    )
                )
                .limit(20)
            )
            return result.scalars().all()

    async def get_all_users(self, limit: int = 100) -> List[User]:
        async with get_session() as session:
            result = await session.execute(
                select(User)
                .order_by(User.id)
                .limit(limit)
            )
            return result.scalars().all()

    async def update_access_level(self, user_id: int, access_level: int) -> None:
        async with get_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(access_level=access_level)
            )
            await session.commit()

    async def update_status(self, user_id: int, status: UserStatus) -> None:
        async with get_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(status=status)
            )
            await session.commit()

    async def update_password(self, user_id: int, password_hash: str) -> None:
        async with get_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(password_hash=password_hash)
            )
            await session.commit()

    async def delete_user(self, user_id: int) -> None:
        async with get_session() as session:
            await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(status=UserStatus.DELETED)
            )
            await session.commit()

    async def update_terminal_settings(
        self,
        user_id: int,
        encoding: Optional[str] = None,
        cols: Optional[int] = None,
        rows: Optional[int] = None
    ) -> None:
        """Update user's terminal preferences"""
        async with get_session() as session:
            values = {}
            if encoding is not None:
                values['encoding_pref'] = encoding
            if cols is not None:
                values['terminal_cols'] = cols
            if rows is not None:
                values['terminal_rows'] = rows

            if values:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(**values)
                )
                await session.commit()


class BoardRepository:
    async def create_board(
        self,
        name: str,
        description: Optional[str] = None,
        min_read: int = 0,
        min_write: int = 1,
    ) -> Board:
        async with get_session() as session:
            board = Board(
                name=name,
                description=description,
                min_read_access=min_read,
                min_write_access=min_write,
                created_at=datetime.utcnow(),
            )
            session.add(board)
            await session.commit()
            await session.refresh(board)
            return board

    async def get_all_boards(self, user_access_level: int = 0) -> List[Board]:
        async with get_session() as session:
            result = await session.execute(
                select(Board)
                .where(Board.min_read_access <= user_access_level)
                .order_by(Board.name)
            )
            return result.scalars().all()

    async def get_board(self, board_id: int) -> Optional[Board]:
        async with get_session() as session:
            result = await session.execute(
                select(Board).where(Board.id == board_id)
            )
            return result.scalar_one_or_none()

    async def get_board_by_name(self, name: str) -> Optional[Board]:
        async with get_session() as session:
            result = await session.execute(
                select(Board).where(Board.name == name)
            )
            return result.scalar_one_or_none()

    async def create_post(
        self,
        board_id: int,
        author_id: int,
        subject: str,
        body: str,
        parent_id: Optional[int] = None,
    ) -> Post:
        async with get_session() as session:
            post = Post(
                board_id=board_id,
                author_id=author_id,
                subject=subject,
                body=body,
                parent_id=parent_id,
                created_at=datetime.utcnow(),
            )
            session.add(post)

            await session.execute(
                update(Board)
                .where(Board.id == board_id)
                .values(
                    post_count=Board.post_count + 1,
                    last_post_at=datetime.utcnow(),
                )
            )

            await session.execute(
                update(User)
                .where(User.id == author_id)
                .values(total_posts=User.total_posts + 1)
            )

            await session.commit()
            await session.refresh(post)
            return post

    async def get_posts(
        self,
        board_id: int,
        offset: int = 0,
        limit: int = 20,
        include_replies: bool = False,
    ) -> List[Post]:
        async with get_session() as session:
            query = (
                select(Post)
                .where(
                    and_(
                        Post.board_id == board_id,
                        Post.is_deleted == False,
                    )
                )
                .order_by(Post.created_at.desc())
                .offset(offset)
                .limit(limit)
            )

            if not include_replies:
                query = query.where(Post.parent_id.is_(None))

            result = await session.execute(query)
            return result.scalars().all()

    async def search_posts(self, query: str, user_access_level: int = 0) -> List[Post]:
        """Search posts by subject or body content"""
        async with get_session() as session:
            # Get boards user can access
            accessible_boards = await session.execute(
                select(Board.id).where(Board.min_read_access <= user_access_level)
            )
            board_ids = [b for (b,) in accessible_boards.fetchall()]

            # Search posts
            result = await session.execute(
                select(Post)
                .where(
                    and_(
                        Post.board_id.in_(board_ids),
                        Post.is_deleted == False,
                        or_(
                            Post.subject.ilike(f"%{query}%"),
                            Post.body.ilike(f"%{query}%")
                        )
                    )
                )
                .order_by(Post.created_at.desc())
                .limit(50)
            )
            return result.scalars().all()


class ChatRepository:
    async def create_room(
        self,
        name: str,
        description: Optional[str] = None,
        min_access: int = 0,
        is_private: bool = False,
    ) -> ChatRoom:
        async with get_session() as session:
            room = ChatRoom(
                name=name,
                description=description,
                min_access=min_access,
                is_private=is_private,
                created_at=datetime.utcnow(),
            )
            session.add(room)
            await session.commit()
            await session.refresh(room)
            return room

    async def get_rooms(self, user_access_level: int = 0) -> List[ChatRoom]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatRoom)
                .where(
                    and_(
                        ChatRoom.min_access <= user_access_level,
                        ChatRoom.is_private == False,
                    )
                )
                .order_by(ChatRoom.name)
            )
            return result.scalars().all()

    async def get_room_by_name(self, name: str) -> Optional[ChatRoom]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatRoom).where(ChatRoom.name == name)
            )
            return result.scalar_one_or_none()

    async def save_message(
        self,
        room_id: int,
        author_id: int,
        body: str,
        is_whisper: bool = False,
        whisper_to_id: Optional[int] = None,
    ) -> ChatMessage:
        async with get_session() as session:
            message = ChatMessage(
                room_id=room_id,
                author_id=author_id,
                body=body,
                is_whisper=is_whisper,
                whisper_to_id=whisper_to_id,
                created_at=datetime.utcnow(),
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message

    async def get_recent_messages(
        self, room_id: int, limit: int = 50
    ) -> List[ChatMessage]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.room_id == room_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )
            messages = result.scalars().all()
            return list(reversed(messages))


class FileRepository:
    async def create_area(
        self,
        name: str,
        path: str,
        description: Optional[str] = None,
        min_access: int = 0,
    ) -> FileArea:
        async with get_session() as session:
            area = FileArea(
                name=name,
                path=path,
                description=description,
                min_access=min_access,
                created_at=datetime.utcnow(),
            )
            session.add(area)
            await session.commit()
            await session.refresh(area)
            return area

    async def get_areas(self, user_access_level: int = 0) -> List[FileArea]:
        async with get_session() as session:
            result = await session.execute(
                select(FileArea)
                .where(FileArea.min_access <= user_access_level)
                .order_by(FileArea.name)
            )
            return result.scalars().all()

    async def create_file(
        self,
        area_id: int,
        filename: str,
        logical_path: str,
        size: int,
        uploader_id: Optional[int] = None,
        description: Optional[str] = None,
        checksum: Optional[str] = None,
    ) -> File:
        async with get_session() as session:
            file = File(
                area_id=area_id,
                filename=filename,
                logical_path=logical_path,
                size=size,
                uploader_id=uploader_id,
                description=description,
                checksum=checksum,
                upload_date=datetime.utcnow(),
            )
            session.add(file)
            await session.commit()
            await session.refresh(file)
            return file

    async def get_files(
        self, area_id: int, offset: int = 0, limit: int = 50
    ) -> List[File]:
        async with get_session() as session:
            result = await session.execute(
                select(File)
                .where(
                    and_(
                        File.area_id == area_id,
                        File.is_deleted == False,
                    )
                )
                .order_by(File.upload_date.desc())
                .offset(offset)
                .limit(limit)
            )
            return result.scalars().all()

    async def log_transfer(
        self,
        user_id: int,
        file_id: Optional[int],
        direction: str,
        protocol: str,
        bytes_transferred: int,
        status: str,
        remote_addr: Optional[str] = None,
    ) -> Transfer:
        async with get_session() as session:
            transfer = Transfer(
                user_id=user_id,
                file_id=file_id,
                direction=direction,
                protocol=protocol,
                bytes_transferred=bytes_transferred,
                status=status,
                remote_addr=remote_addr,
                started_at=datetime.utcnow(),
            )
            session.add(transfer)
            await session.commit()
            await session.refresh(transfer)
            return transfer

    async def increment_download_count(self, file_id: int) -> None:
        async with get_session() as session:
            await session.execute(
                update(File)
                .where(File.id == file_id)
                .values(download_count=File.download_count + 1)
            )
            await session.commit()

    async def get_area(self, area_id: int) -> Optional[FileArea]:
        async with get_session() as session:
            result = await session.execute(
                select(FileArea).where(FileArea.id == area_id)
            )
            return result.scalar_one_or_none()

    async def search_files(self, query: str, user_access_level: int = 0) -> List[File]:
        """Search files by filename or description"""
        async with get_session() as session:
            # Get areas user can access
            accessible_areas = await session.execute(
                select(FileArea.id).where(FileArea.min_access <= user_access_level)
            )
            area_ids = [a for (a,) in accessible_areas.fetchall()]

            # Search files
            result = await session.execute(
                select(File)
                .where(
                    and_(
                        File.area_id.in_(area_ids),
                        File.is_deleted == False,
                        or_(
                            File.filename.ilike(f"%{query}%"),
                            File.description.ilike(f"%{query}%")
                        )
                    )
                )
                .order_by(File.upload_date.desc())
                .limit(50)
            )
            return result.scalars().all()

    async def search_files_with_areas(
        self, query: str, user_access_level: int = 0
    ) -> List[tuple]:
        """Search files with area names included (avoids N+1 queries).

        Returns list of (File, area_name) tuples.
        """
        async with get_session() as session:
            # Search files with a JOIN to get area names in a single query
            result = await session.execute(
                select(File, FileArea.name)
                .join(FileArea, File.area_id == FileArea.id)
                .where(
                    and_(
                        FileArea.min_access <= user_access_level,
                        File.is_deleted == False,
                        or_(
                            File.filename.ilike(f"%{query}%"),
                            File.description.ilike(f"%{query}%")
                        )
                    )
                )
                .order_by(File.upload_date.desc())
                .limit(50)
            )
            return result.all()


class SystemRepository:
    async def get_stats(self) -> dict:
        """Get system statistics.

        NOTE: This method issues multiple sequential COUNT queries which
        may become slow as the database grows. For better performance at
        scale, consider:
        1. Caching stats with a short TTL (e.g., 60 seconds)
        2. Using a single query with subqueries
        3. Maintaining a stats table updated by triggers
        4. Running counts in parallel with asyncio.gather()
        """
        async with get_session() as session:
            total_users = await session.scalar(
                select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
            )
            active_sessions = await session.scalar(
                select(func.count(SessionModel.id)).where(SessionModel.ended_at.is_(None))
            )
            total_posts = await session.scalar(
                select(func.count(Post.id)).where(Post.is_deleted == False)
            )
            total_files = await session.scalar(
                select(func.count(File.id)).where(File.is_deleted == False)
            )
            total_downloads = await session.scalar(
                select(func.count(Transfer.id)).where(Transfer.direction == "download")
            )

            return {
                "total_users": total_users or 0,
                "active_sessions": active_sessions or 0,
                "total_posts": total_posts or 0,
                "total_files": total_files or 0,
                "total_downloads": total_downloads or 0,
                "version": "0.1.0",
            }

    async def get_detailed_stats(self) -> dict:
        async with get_session() as session:
            stats = await self.get_stats()

            # Additional detailed stats
            active_users = await session.scalar(
                select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
            )
            banned_users = await session.scalar(
                select(func.count(User.id)).where(User.status == UserStatus.BANNED)
            )
            total_boards = await session.scalar(
                select(func.count(Board.id))
            )
            total_uploads = await session.scalar(
                select(func.count(Transfer.id)).where(Transfer.direction == "upload")
            )

            stats.update({
                "active_users": active_users or 0,
                "banned_users": banned_users or 0,
                "total_boards": total_boards or 0,
                "total_uploads": total_uploads or 0,
                "uptime": "N/A",  # Would need to track server start time
                "storage_used": "N/A",  # Would need filesystem access
                "db_size": "N/A",  # Would need DB-specific query
            })

            return stats


class MailRepository:
    """Repository for private mail operations"""

    async def send_message(
        self,
        sender_id: int,
        recipient_id: int,
        subject: str,
        body: str
    ) -> Optional[PrivateMessage]:
        try:
            async with get_session() as session:
                message = PrivateMessage(
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    subject=subject,
                    body=body,
                    created_at=datetime.utcnow()
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)
                return message
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None

    async def get_inbox(self, user_id: int, include_deleted: bool = False) -> List[PrivateMessage]:
        async with get_session() as session:
            query = select(PrivateMessage).where(
                PrivateMessage.recipient_id == user_id
            )

            if not include_deleted:
                query = query.where(PrivateMessage.is_deleted_recipient == False)

            query = query.order_by(PrivateMessage.created_at.desc())

            result = await session.execute(query)
            return result.scalars().all()

    async def get_sent(self, user_id: int, include_deleted: bool = False) -> List[PrivateMessage]:
        async with get_session() as session:
            query = select(PrivateMessage).where(
                PrivateMessage.sender_id == user_id
            )

            if not include_deleted:
                query = query.where(PrivateMessage.is_deleted_sender == False)

            query = query.order_by(PrivateMessage.created_at.desc())

            result = await session.execute(query)
            return result.scalars().all()

    async def get_message(self, message_id: int) -> Optional[PrivateMessage]:
        async with get_session() as session:
            result = await session.execute(
                select(PrivateMessage).where(PrivateMessage.id == message_id)
            )
            return result.scalar_one_or_none()

    async def mark_as_read(self, message_id: int) -> None:
        async with get_session() as session:
            await session.execute(
                update(PrivateMessage)
                .where(PrivateMessage.id == message_id)
                .values(read_at=datetime.utcnow())
            )
            await session.commit()

    async def delete_message(self, message_id: int, user_id: int) -> None:
        """Soft delete a message for a user"""
        async with get_session() as session:
            message = await session.execute(
                select(PrivateMessage).where(PrivateMessage.id == message_id)
            )
            msg = message.scalar_one_or_none()

            if msg:
                if msg.sender_id == user_id:
                    await session.execute(
                        update(PrivateMessage)
                        .where(PrivateMessage.id == message_id)
                        .values(is_deleted_sender=True)
                    )
                elif msg.recipient_id == user_id:
                    await session.execute(
                        update(PrivateMessage)
                        .where(PrivateMessage.id == message_id)
                        .values(is_deleted_recipient=True)
                    )

                await session.commit()

    async def get_unread_count(self, user_id: int) -> int:
        async with get_session() as session:
            count = await session.scalar(
                select(func.count(PrivateMessage.id))
                .where(
                    and_(
                        PrivateMessage.recipient_id == user_id,
                        PrivateMessage.read_at.is_(None),
                        PrivateMessage.is_deleted_recipient == False
                    )
                )
            )
            return count or 0