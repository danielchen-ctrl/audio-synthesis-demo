"""精简后处理（3A 路线）：关键词注入 + 中文稳定化。

repair_dialogue_quality 不迁移——云 LLM 不产生 Bundle 特有退化问题，
repair 遍对云 LLM 输出无作用对象（PR #36 评估结论）。

失败时只记 warning，不阻断主流程。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def apply_postprocess(
    lines: list[tuple[str, str]],
    language: str,
    keywords: list[str] | None = None,
    speaker_count: int = 2,
    title: str = "",
    scenario: str = "",
    core_content: str = "",
    target_word_count: int = 1000,
) -> list[tuple[str, str]]:
    """精简后处理：稳定化 + 关键词注入。

    Args:
        lines:            [(speaker_id, text), ...] 对话行
        language:         语言代码，如 "zh" / "en"
        keywords:         需要注入的关键词列表
        speaker_count:    说话人数（stabilize 需要）
        title/scenario/core_content: 主题上下文（给 keywords 注入提供语境）
        target_word_count: 目标字数（给 stabilize 使用）

    Returns:
        处理后的对话行（失败时返回原始 lines）
    """
    try:
        from app.services.multilingual_naturalness_lite import (
            enforce_keywords_in_lines,
            stabilize_dialogue_constraints,
        )

        # 1. 关键词注入（所有语言）
        if keywords:
            lines, _ = enforce_keywords_in_lines(
                lines, keywords, language,
                title=title, scenario=scenario, core_content=core_content,
            )

        # 2. 中文稳定化（非中文 early return，无副作用）
        lines, _ = stabilize_dialogue_constraints(
            lines, language,
            title=title, scenario=scenario, core_content=core_content,
            target_word_count=target_word_count,
            people_count=speaker_count,
            keywords=keywords or [],
        )

    except Exception as exc:
        logger.warning("后处理异常（已跳过，使用原始输出）: %s", exc)

    return lines
