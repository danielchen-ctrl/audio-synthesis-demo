"""预设主题模板加载与查询。

数据源：app/data/preset_topics.json（从 audio-synthesis-demo-main 同步而来）。
启动时一次性加载到内存。修改文件需要重启服务。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "preset_topics.json"


@lru_cache
def load_preset_topics() -> list[dict[str, Any]]:
    """全部预设主题列表（首次调用后缓存）。"""
    if not _DATA_PATH.exists():
        return []
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_preset_by_id(topic_id: str) -> dict[str, Any] | None:
    for t in load_preset_topics():
        if str(t.get("id")) == str(topic_id):
            return t
    return None


def is_valid_template_code(code: str) -> bool:
    """code 可以是 'custom' 或预设的 id 字符串。"""
    if code == "custom":
        return True
    return get_preset_by_id(code) is not None
