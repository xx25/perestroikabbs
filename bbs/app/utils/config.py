import os
from pathlib import Path
from typing import Any, Dict, Optional

import toml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from ..exceptions import ConfigurationError


class ServerConfig(BaseModel):
    """Server configuration with validation."""

    host: str = "0.0.0.0"
    port: int = 2323
    motd_asset: str = "ansi/motd.ans"
    max_connections: int = 100
    connection_timeout: int = 300
    welcome_message: str = "Welcome to Perestroika BBS!"

    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ConfigurationError(f"Port must be 1-65535, got {v}")
        return v

    @field_validator('max_connections')
    @classmethod
    def validate_max_connections(cls, v: int) -> int:
        if v < 1:
            raise ConfigurationError("max_connections must be positive")
        if v > 10000:
            raise ConfigurationError("max_connections too high (max 10000)")
        return v

    @field_validator('connection_timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 0:
            raise ConfigurationError("connection_timeout cannot be negative")
        return v


class TelnetConfig(BaseModel):
    enable_naws: bool = True
    enable_binary: bool = True
    enable_echo: bool = False
    default_cols: int = 80
    default_rows: int = 24


class DatabaseConfig(BaseModel):
    """Database configuration with validation."""

    dsn: str
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600

    @field_validator('dsn')
    @classmethod
    def validate_dsn(cls, v: str) -> str:
        if not v.startswith(('mysql', 'postgresql', 'sqlite')):
            raise ConfigurationError(f"Unsupported database driver: {v.split(':')[0]}")
        return v

    @field_validator('pool_size')
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        if v < 1:
            raise ConfigurationError("pool_size must be positive")
        if v > 100:
            raise ConfigurationError("pool_size too high (max 100)")
        return v

    @model_validator(mode='after')
    def validate_pool_settings(self):
        """Validate pool settings are reasonable together."""
        total = self.pool_size + self.max_overflow
        if total > 200:
            raise ConfigurationError(
                f"Total pool connections ({total}) too high (max 200)"
            )
        return self


class TransferConfig(BaseModel):
    rz_path: str = "/usr/bin/rz"
    sz_path: str = "/usr/bin/sz"
    ckermit_path: str = "/usr/bin/kermit"
    download_root: str = "/var/lib/bbs/files"
    upload_root: str = "/var/lib/bbs/uploads"
    max_upload_size: int = 10485760
    allowed_extensions: list[str] = Field(default_factory=lambda: [
        ".txt", ".zip", ".arc", ".lha", ".gif", ".jpg", ".png", ".ans", ".rip"
    ])


class SecurityConfig(BaseModel):
    """Security configuration with validation."""

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4
    max_login_attempts: int = 5
    login_throttle_seconds: int = 60
    session_timeout: int = 3600
    require_secure_passwords: bool = True
    min_password_length: int = 8

    @field_validator('min_password_length')
    @classmethod
    def validate_min_password_length(cls, v: int) -> int:
        if v < 6:
            raise ConfigurationError("min_password_length must be at least 6")
        if v > 128:
            raise ConfigurationError("min_password_length too high (max 128)")
        return v

    @field_validator('argon2_memory_cost')
    @classmethod
    def validate_argon2_memory(cls, v: int) -> int:
        if v < 8192:
            raise ConfigurationError("argon2_memory_cost too low (min 8192)")
        if v > 1048576:
            raise ConfigurationError("argon2_memory_cost too high (max 1048576)")
        return v


class CharsetConfig(BaseModel):
    default_encoding: str = "utf-8"
    supported_encodings: list[str] = Field(default_factory=lambda: [
        "utf-8", "cp437", "iso-8859-1", "iso-8859-2", "iso-8859-5",
        "iso-8859-7", "koi8-r", "windows-1251", "windows-1252",
        "macintosh", "shift_jis"
    ])


class LanguageConfig(BaseModel):
    default_language: str = "en"
    supported_languages: list[str] = Field(default_factory=lambda: ["en", "ru"])


class ChatConfig(BaseModel):
    max_message_length: int = 500
    max_rooms: int = 50
    default_room: str = "main"
    enable_whispers: bool = True
    enable_moderator_channel: bool = True
    transcript_batch_size: int = 100
    transcript_batch_interval: int = 60


class BoardsConfig(BaseModel):
    max_subject_length: int = 100
    max_post_length: int = 10000
    posts_per_page: int = 20
    enable_attachments: bool = True
    max_attachment_size: int = 1048576
    enable_moderation: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = "/var/log/bbs/perestroika.log"
    max_bytes: int = 10485760
    backup_count: int = 5
    enable_syslog: bool = False


class RipscripConfig(BaseModel):
    enable: bool = True
    detect_signature: bool = True
    fallback_to_ansi: bool = True
    asset_cache_size: int = 100


class Config(BaseSettings):
    server: ServerConfig = Field(default_factory=ServerConfig)
    telnet: TelnetConfig = Field(default_factory=TelnetConfig)
    db: DatabaseConfig = Field(default_factory=lambda: DatabaseConfig(
        dsn="mysql+aiomysql://bbs_user:password@127.0.0.1:3306/perestroika_bbs"
    ))
    transfers: TransferConfig = Field(default_factory=TransferConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    charset: CharsetConfig = Field(default_factory=CharsetConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    boards: BoardsConfig = Field(default_factory=BoardsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ripscrip: RipscripConfig = Field(default_factory=RipscripConfig)

    class Config:
        env_file = ".env"
        env_prefix = "BBS_"
        env_nested_delimiter = "__"

    @classmethod
    def from_toml(cls, path: str | Path) -> "Config":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            data = toml.load(f)

        return cls(**data)


_config: Optional[Config] = None


def load_config(path: Optional[str | Path] = None) -> Config:
    global _config
    if _config is None:
        if path is None:
            path = os.environ.get("BBS_CONFIG", "config.toml")

        config_path = Path(path)
        if config_path.exists():
            _config = Config.from_toml(config_path)
        else:
            _config = Config()

    return _config


def get_config() -> Config:
    if _config is None:
        return load_config()
    return _config