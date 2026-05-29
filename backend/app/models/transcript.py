"""对话脚本：段级时间码 + 可选 JSON/SRT 文件。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audio_files.file_id", ondelete="CASCADE"),
        primary_key=True,
    )
    segments: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    json_storage_key: Mapped[str | None] = mapped_column(String(512))
    srt_storage_key: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
