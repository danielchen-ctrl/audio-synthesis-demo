#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Few-shot 示例选择器
===================
从训练语料库（demo/training_long_dialogue/）中检索同行业、同语言的对话片段，
注入到生成请求的 core_content 中，引导 LLM 对齐行业对话风格。

用法：
    from demo_app.few_shot_selector import get_few_shot_example
    excerpt = get_few_shot_example(domain="人工智能/科技", language="Chinese")
    # → "Speaker 1: ...\nSpeaker 2: ..." 或 "" (无匹配文件时)
"""

import re
import random
from pathlib import Path

# ─── 路径 ─────────────────────────────────────────────────────────────────
_ROOT         = Path(__file__).resolve().parents[2]
_TRAINING_DIR = _ROOT / "demo" / "training_long_dialogue"

# ─── 领域 → 训练文件 ID ───────────────────────────────────────────────────
_DOMAIN_TO_ID: dict[str, str] = {
    "人工智能/科技":   "ai_tech",
    "娱乐/媒体":       "media_strategy",
    "商业化":          "commercialization",
    "测试开发":        "test_dev",
    "人力资源与招聘":  "hr_recruit",
    "建筑与工程行业":  "construction",
    "咨询/专业服务":   "consulting",
    "法律服务":        "legal",
    "金融/投资":       "finance",
    "零售行业":        "retail",
    "保险行业":        "insurance",
    "医疗行业":        "medical",
    "医疗健康":        "medical",   # alias
    "房地产":          "realestate",
    "制造业":          "manufacturing",
}

# ─── 语言 → 文件名 short code ─────────────────────────────────────────────
_LANG_TO_SHORT: dict[str, str] = {
    "Chinese":    "zh",
    "中文":       "zh",
    "English":    "en",
    "英语":       "en",
    "Japanese":   "ja",
    "日语":       "ja",
    "日本語":     "ja",
    "Korean":     "ko",
    "韩语":       "ko",
    "한국어":     "ko",
    "French":     "fr",
    "法语":       "fr",
    "German":     "de",
    "德语":       "de",
    "Spanish":    "es",
    "西班牙语":   "es",
    "Portuguese": "pt",
    "葡萄牙语":   "pt",
    "Cantonese":  "yue",
    "粤语":       "yue",
}

# 每次注入的最大字符数（太长会稀释 prompt 指令）
_MAX_EXCERPT_CHARS = 500

# 采样时跳过文件头部的比例（避免每次都取开头的客套话）
_SKIP_HEAD_RATIO = 0.2

# 英文/韩文文件 CJK 污染阈值：超过此比例则视为不可用（韩语用 Hangul，汉字为污染）
_MAX_CJK_RATIO_FOR_EN = 0.05

# 英文文件重复句检测阈值：同一行内容出现超过此次数则视为低质量（fallback 刷屏）
_MAX_REPEAT_LINES_EN = 4

# 最多尝试几个候选文件
_MAX_CANDIDATE_TRIES = 4


def _cjk_ratio(text: str) -> float:
    """Fraction of non-whitespace chars in CJK Unified Ideographs (U+4E00–U+9FFF)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\u4e00" <= c <= "\u9fff") / len(chars)


def _hangul_ratio(text: str) -> float:
    """Fraction of non-whitespace chars that are Hangul syllables (U+AC00–U+D7A3)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\uac00" <= c <= "\ud7a3") / len(chars)


def _extract_excerpt(lines: list[str]) -> str:
    """
    从 lines 中随机采样一段不重复的对话片段。
    - 从文件 20% 处随机起跳，避免固定取开头
    - 去掉跨片段重复行（同一内容出现多次时只保留首次）
    - 控制总长度在 _MAX_EXCERPT_CHARS 以内
    """
    total     = len(lines)
    skip_head = max(0, int(total * _SKIP_HEAD_RATIO))
    max_start = max(skip_head, total - 30)
    start     = random.randint(skip_head, max_start)

    # 去重：提取对话内容部分（去掉 Speaker N: 前缀），跳过已见过的内容
    seen_contents: set[str] = set()
    excerpt_lines: list[str] = []
    chars = 0

    for line in lines[start:]:
        # Skip template marker lines that occasionally leak from LLM prompt echoing
        if "<<" in line or ">>" in line:
            continue
        content = re.sub(r"^(Speaker|说话人)\s*\d+:\s*", "", line).strip()
        if content in seen_contents:
            continue
        seen_contents.add(content)

        if chars + len(line) + 1 > _MAX_EXCERPT_CHARS:
            break
        excerpt_lines.append(line)
        chars += len(line) + 1

    return "\n".join(excerpt_lines)


def get_few_shot_example(domain: str, language: str) -> str:
    """
    返回一段训练语料中的对话片段（纯文本，含 Speaker N: 格式）。
    无匹配文件或读取失败时返回空字符串，不抛异常。

    参数：
        domain   - generation_context["domain"]，如 "人工智能/科技"
        language - 规范化语言名，如 "Chinese" / "English" / "Japanese" / "Korean"
    """
    template_id = _DOMAIN_TO_ID.get(domain)
    lang_short  = _LANG_TO_SHORT.get(language)

    if not template_id or not lang_short:
        return ""

    # Language quality filters:
    # - English: reject files with CJK contamination (Chinese bleed-in)
    # - Korean:  confirm Hangul presence (Korean script, outside CJK range)
    # - Japanese: confirm kana presence (hiragana/katakana).  Japanese uses CJK for
    #   kanji but legitimate JA text always has kana for grammar particles/endings.
    #   All-CJK-no-kana files are Chinese-contaminated and must not be injected into
    #   the prompt (they would push the LLM toward generating Chinese).
    needs_cjk_filter = lang_short in ("en", "ko", "ja")

    # 优先用 wc5000（最短，context 压力最小），偏好 spk3（轮次分布均衡）
    candidates: list[Path] = []
    for spk in [3, 2, 4, 5]:
        p = _TRAINING_DIR / f"{template_id}_{lang_short}_spk{spk}_wc5000.txt"
        if p.exists():
            candidates.append(p)

    if not candidates:
        candidates = sorted(
            _TRAINING_DIR.glob(f"{template_id}_{lang_short}_spk*_wc5000.txt")
        )

    if not candidates:
        return ""

    # 语言质量过滤：
    #   English:  CJK ratio ≤ 5%（排除中文污染）+ repetition check
    #   Korean:   Hangul ratio ≥ 8%（确认韩文内容存在）
    #   Japanese: kana (hiragana+katakana) ratio ≥ 5%（确认假名存在；全汉字无假名=中文污染）
    if needs_cjk_filter:
        clean_candidates: list[Path] = []
        for p in candidates:
            try:
                sample = p.read_text(encoding="utf-8")[:2000]
                if lang_short == "ko":
                    # Korean: confirm Hangul presence rather than CJK absence
                    if _hangul_ratio(sample) >= 0.08:
                        clean_candidates.append(p)
                elif lang_short == "ja":
                    # Japanese: confirm kana presence (hiragana U+3040-U+309F, katakana U+30A0-U+30FF)
                    non_ws = [c for c in sample if not c.isspace()]
                    kana_count = sum(1 for c in non_ws if "\u3040" <= c <= "\u30ff")
                    if non_ws and kana_count / len(non_ws) >= 0.05:
                        clean_candidates.append(p)
                else:
                    # English: reject files with CJK contamination or repetitive fallback content
                    if _cjk_ratio(sample) > _MAX_CJK_RATIO_FOR_EN:
                        continue
                    # Check for repetitive fallback patterns (LLM drift artifacts)
                    lines = [l for l in sample.splitlines() if l.strip()]
                    contents = [re.sub(r"^(Speaker|说話人)\s*\d+:\s*", "", l).strip() for l in lines]
                    from collections import Counter
                    if contents:
                        most_common_count = Counter(contents).most_common(1)[0][1]
                        if most_common_count > _MAX_REPEAT_LINES_EN:
                            continue  # skip repetitive file
                    clean_candidates.append(p)
            except Exception:
                pass
        if clean_candidates:
            candidates = clean_candidates
        else:
            return ""

    # 随机从候选中取，最多尝试 _MAX_CANDIDATE_TRIES 个
    tried = set()
    for _ in range(min(_MAX_CANDIDATE_TRIES, len(candidates))):
        remaining = [p for p in candidates if p not in tried]
        if not remaining:
            break
        path = random.choice(remaining)
        tried.add(path)
        try:
            text  = path.read_text(encoding="utf-8")
            lines = [l for l in text.splitlines() if l.strip()]
            if not lines:
                continue
            excerpt = _extract_excerpt(lines)
            if excerpt:
                return excerpt
        except Exception:
            continue

    return ""
