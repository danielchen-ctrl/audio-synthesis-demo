"""lang_utils.py — shared language normalisation helpers.

Single source of truth for the language alias map and canonical_language().
Both embedded_server_main and multilingual_naturalness import from here.
"""
from __future__ import annotations

# Superset of all aliases used across the codebase (ISO codes + Chinese names +
# native-script names + English names).
LANGUAGE_ALIASES: dict[str, str] = {
    # Chinese
    "中文": "Chinese", "中文（普通话）": "Chinese",
    "Chinese": "Chinese", "zh": "Chinese",
    # English
    "英语": "English", "英文": "English",
    "English": "English", "en": "English",
    # Japanese
    "日语": "Japanese", "日本語": "Japanese",
    "Japanese": "Japanese", "ja": "Japanese",
    # Korean
    "韩语": "Korean", "한국어": "Korean",
    "Korean": "Korean", "ko": "Korean",
    # French
    "法语": "French", "French": "French", "fr": "French",
    # German
    "德语": "German", "Deutsch": "German",
    "German": "German", "de": "German",
    # Spanish
    "西班牙语": "Spanish", "Español": "Spanish",
    "Spanish": "Spanish", "es": "Spanish",
    # Portuguese
    "葡萄牙语": "Portuguese", "Português": "Portuguese",
    "Portuguese": "Portuguese", "pt": "Portuguese",
    # Italian
    "意大利语": "Italian", "Italian": "Italian", "it": "Italian",
    # Russian
    "俄语": "Russian", "Russian": "Russian", "ru": "Russian",
    # Arabic
    "阿拉伯语": "Arabic", "Arabic": "Arabic", "ar": "Arabic",
    # Indonesian
    "印度尼西亚语": "Indonesian", "印尼语": "Indonesian",
    "Indonesian": "Indonesian", "id": "Indonesian",
    # Cantonese
    "粤语": "Cantonese", "Cantonese": "Cantonese",
}


def canonical_language(value: str) -> str:
    """Normalise any language name/code to its canonical English form.

    Falls back to "Chinese" for unrecognised values (matches historical behaviour).
    """
    return LANGUAGE_ALIASES.get(str(value).strip(), "Chinese")
