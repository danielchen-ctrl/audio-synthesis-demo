"""统一日志配置：结构化、彩色（dev）/JSON（prod）。"""
from __future__ import annotations

import sys

from loguru import logger

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    logger.remove()

    if settings.APP_ENV == "production":
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            serialize=True,  # JSON output
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}:{function}:{line}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
