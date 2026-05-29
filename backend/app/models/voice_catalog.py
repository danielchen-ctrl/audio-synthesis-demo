"""音色目录表。

voice_catalog 是平台音色库的唯一权威来源：
- 所有用户共享，任何登录用户均可查看并使用
- 仅创建者可删除自己注册的音色
- is_deleted 软删除（不物理删除，保留审计轨迹）
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class VoiceCatalog(Base):
    __tablename__ = "voice_catalog"

    voice_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="CosyVoice 返回的 voice_id"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="用户起的名字，如「耿同学」"
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="语言代码：zh / en / ..."
    )
    gender: Mapped[str | None] = mapped_column(
        String(10), comment="male / female / neutral"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者 user_id（审计用途，非权限控制主键）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="软删除标志"
    )
