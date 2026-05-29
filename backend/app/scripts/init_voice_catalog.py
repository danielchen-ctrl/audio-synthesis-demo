"""启动时初始化音色目录。

若 voice_catalog 表为空，自动从 CosyVoice /v1/voices/custom 拉取一次做导入。
失败时只记 warning，不阻断 API 启动。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def init_voice_catalog_if_empty() -> None:
    """若表为空则从 CosyVoice 导入初始音色列表。"""
    from app.core.db import SessionLocal
    from app.models.voice_catalog import VoiceCatalog
    from app.providers.tts.factory import get_tts_provider

    with SessionLocal() as db:
        count = db.query(VoiceCatalog).filter_by(is_deleted=False).count()
        if count > 0:
            logger.info(f"Voice catalog already has {count} entries, skipping init.")
            return

        provider = get_tts_provider()
        voices = provider.list_voices()
        if not voices:
            logger.warning("CosyVoice returned empty voice list during init.")
            return

        for v in voices:
            existing = db.query(VoiceCatalog).filter_by(voice_id=v.voice_id).first()
            if existing:
                continue
            db.add(VoiceCatalog(
                voice_id=v.voice_id,
                name=v.name,
                language=v.language,
                gender=v.gender,
            ))
        db.commit()
        logger.info(f"Voice catalog initialized with {len(voices)} voices from CosyVoice.")
