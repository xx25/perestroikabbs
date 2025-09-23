import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .config import get_config


def setup_logging(name: str = "bbs") -> logging.Logger:
    config = get_config()
    log_config = config.logging

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_config.level))
    logger.handlers.clear()

    formatter = logging.Formatter(log_config.format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_config.file_path:
        log_path = Path(log_config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=log_config.max_bytes,
            backupCount=log_config.backup_count,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"bbs.{name}")