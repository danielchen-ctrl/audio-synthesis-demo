"""元数据 API：语种 / 音色 / 主题模板 / 场景。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.models import Tag
from app.providers.tts import VoiceSpec, get_tts_provider
from app.providers.tts.factory import get_fallback_voices

router = APIRouter()


@router.get("/languages")
def list_languages() -> list[dict[str, str]]:
    """对应 PRD §6.1 的 12 种语言。"""
    return [
        {"code": "zh", "name": "中文（普通话）"},
        {"code": "en", "name": "英语"},
        {"code": "ja", "name": "日语"},
        {"code": "ko", "name": "韩语"},
        {"code": "es", "name": "西班牙语"},
        {"code": "fr", "name": "法语"},
        {"code": "de", "name": "德语"},
        {"code": "pt", "name": "葡萄牙语"},
        {"code": "it", "name": "意大利语"},
        {"code": "ru", "name": "俄语"},
        {"code": "ar", "name": "阿拉伯语"},
        {"code": "id", "name": "印度尼西亚语"},
    ]


@router.get("/templates")
def list_templates() -> list[dict]:
    """主题模板：22 条预设（来自 audio-synthesis-demo-main）+ 自定义入口。

    返回结构：
      [{code, name, description, roles, core_keywords,
        example_topic, default_speaker_count, default_target_words}, ...]
    """
    from app.services.preset_topics import load_preset_topics

    out: list[dict] = []
    for t in load_preset_topics():
        out.append({
            "code": str(t["id"]),
            "name": t.get("label", ""),
            "description": t.get("topic_description", ""),
            "roles": t.get("roles", []),
            "core_keywords": t.get("core_keywords", []),
            "example_topic": t.get("example_topic", ""),
            "default_speaker_count": t.get("people_count", 2),
            "default_target_words": t.get("target_words", 1500),
        })
    # 自定义入口始终在最后
    out.append({
        "code": "custom",
        "name": "自定义",
        "description": "用户自由描述生成需求；生成时使用您填写的 Prompt",
        "roles": [],
        "core_keywords": [],
        "example_topic": "",
        "default_speaker_count": 2,
        "default_target_words": 1500,
    })
    return out


@router.get("/scenes")
def list_scenes() -> list[dict[str, str]]:
    return [
        {"code": "meeting", "name": "会议讨论"},
        {"code": "interview", "name": "访谈"},
        {"code": "medical", "name": "问诊"},
        {"code": "custom", "name": "自定义"},
        {"code": "other", "name": "其他"},
    ]


@router.get("/tags")
def list_tags(
    current_user: CurrentUser,
    db: DbSession,
    q: str | None = Query(None, description="按名字模糊匹配"),
) -> list[dict]:
    """所有已存在的标签（全平台共享）。前端做自动补全用。"""
    query = db.query(Tag).order_by(Tag.name)
    if q:
        query = query.filter(Tag.name.ilike(f"%{q}%"))
    return [{"tag_id": str(t.tag_id), "name": t.name} for t in query.limit(100).all()]


@router.get("/voices")
def list_voices(language: str | None = Query(None, description="按语言过滤")) -> list[dict]:
    """从 CosyVoice 拉音色目录；失败时返回回退列表。"""
    provider = get_tts_provider()
    voices: list[VoiceSpec] = provider.list_voices(language=language)
    if not voices:
        voices = get_fallback_voices()
        if language:
            voices = [v for v in voices if v.language == language]
    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "language": v.language,
            "gender": v.gender,
        }
        for v in voices
    ]
