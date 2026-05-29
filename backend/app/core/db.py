"""SQLAlchemy engine + session + Base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=settings.APP_ENV == "development" and False,  # 需要时改 True
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """ORM base class."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：每个请求一个 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
