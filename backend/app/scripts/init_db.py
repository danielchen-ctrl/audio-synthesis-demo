"""一次性初始化 DB：建表 + 可选创建管理员账号。

运行: python -m app.scripts.init_db
"""
from __future__ import annotations

import os
import sys

from loguru import logger

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import AudioFile, Folder, Tag, Task, User  # noqa: F401  确保模型被导入注册


def init_tables() -> None:
    logger.info("Creating tables ...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created.")


def create_admin_if_missing() -> None:
    """如果设置了环境变量 INIT_ADMIN_USER / INIT_ADMIN_PASSWORD，则创建一个初始账号。"""
    admin_user = os.getenv("INIT_ADMIN_USER")
    admin_pwd = os.getenv("INIT_ADMIN_PASSWORD")
    if not admin_user or not admin_pwd:
        logger.info("跳过初始账号创建（未设置 INIT_ADMIN_USER / INIT_ADMIN_PASSWORD）")
        return
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == admin_user).first()
        if existing:
            logger.info(f"账号 {admin_user} 已存在，跳过")
            return
        u = User(
            username=admin_user,
            password_hash=hash_password(admin_pwd),
            display_name="Admin",
        )
        db.add(u)
        db.commit()
        logger.info(f"初始账号已创建: {admin_user}")
    finally:
        db.close()


def main() -> int:
    init_tables()
    create_admin_if_missing()
    return 0


if __name__ == "__main__":
    sys.exit(main())
