from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON, BigInteger, Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class UserStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(32), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    real_name = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)
    access_level = Column(Integer, default=1, nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    language_pref = Column(String(5), default="en")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0)
    total_posts = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    total_uploads = Column(Integer, default=0)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    messages = relationship("PrivateMessage", foreign_keys="PrivateMessage.sender_id", back_populates="sender")
    received_messages = relationship("PrivateMessage", foreign_keys="PrivateMessage.recipient_id", back_populates="recipient")
    uploads = relationship("File", back_populates="uploader")
    # chat_messages relationship handled by ChatMessage model to avoid ambiguity

    __table_args__ = (
        Index("idx_user_status_login", "status", "last_login_at"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    remote_addr = Column(String(45), nullable=True)
    remote_port = Column(Integer, nullable=True)
    client_info = Column(String(255), nullable=True)
    terminal_cols = Column(Integer, default=80)
    terminal_rows = Column(Integer, default=24)
    capabilities_json = Column(JSON, nullable=True)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_session_user_time", "user_id", "started_at"),
    )


class Board(Base):
    __tablename__ = "boards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    min_read_access = Column(Integer, default=0)
    min_write_access = Column(Integer, default=1)
    post_count = Column(Integer, default=0)
    last_post_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="board", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_id = Column(Integer, ForeignKey("boards.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    subject = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    edited_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)

    board = relationship("Board", back_populates="posts")
    author = relationship("User", back_populates="posts")
    parent = relationship("Post", remote_side=[id])
    replies = relationship("Post", back_populates="parent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_post_board_created", "board_id", "created_at"),
        Index("idx_post_author", "author_id"),
    )


class PrivateMessage(Base):
    __tablename__ = "private_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)
    is_deleted_sender = Column(Boolean, default=False)
    is_deleted_recipient = Column(Boolean, default=False)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="messages")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")

    __table_args__ = (
        Index("idx_message_recipient_read", "recipient_id", "read_at"),
        Index("idx_message_sender", "sender_id"),
    )


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    min_access = Column(Integer, default=0)
    is_private = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_whisper = Column(Boolean, default=False)
    whisper_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    room = relationship("ChatRoom", back_populates="messages")
    author = relationship("User", foreign_keys=[author_id])
    whisper_to = relationship("User", foreign_keys=[whisper_to_id])

    __table_args__ = (
        Index("idx_chat_room_created", "room_id", "created_at"),
    )


class FileArea(Base):
    __tablename__ = "file_areas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    path = Column(String(255), nullable=False)
    min_access = Column(Integer, default=0)
    allow_upload = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("File", back_populates="area", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    area_id = Column(Integer, ForeignKey("file_areas.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    logical_path = Column(String(512), nullable=False)
    size = Column(BigInteger, nullable=False)
    checksum = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    download_count = Column(Integer, default=0)
    min_access = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)

    area = relationship("FileArea", back_populates="files")
    uploader = relationship("User", back_populates="uploads")
    transfers = relationship("Transfer", back_populates="file")

    __table_args__ = (
        UniqueConstraint("area_id", "filename", name="uq_area_filename"),
        Index("idx_file_area_name", "area_id", "filename"),
    )


class TransferProtocol(Enum):
    XMODEM = "xmodem"
    XMODEM_1K = "xmodem_1k"
    ZMODEM = "zmodem"
    KERMIT = "kermit"


class TransferDirection(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"


class TransferStatus(Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    direction = Column(SQLEnum(TransferDirection), nullable=False)
    protocol = Column(SQLEnum(TransferProtocol), nullable=False)
    bytes_transferred = Column(BigInteger, default=0)
    total_bytes = Column(BigInteger, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(TransferStatus), default=TransferStatus.STARTED)
    error_message = Column(String(255), nullable=True)
    remote_addr = Column(String(45), nullable=True)

    user = relationship("User")
    file = relationship("File", back_populates="transfers")

    __table_args__ = (
        Index("idx_transfer_user_time", "user_id", "started_at"),
    )


class AnsiAsset(Base):
    __tablename__ = "ansi_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False)
    variant = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("key", "variant", name="uq_asset_key_variant"),
    )


class RipAsset(Base):
    __tablename__ = "rip_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Config(Base):
    __tablename__ = "config"

    key = Column(String(100), primary_key=True)
    value_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)