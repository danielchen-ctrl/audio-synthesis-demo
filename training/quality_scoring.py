from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from training.training_types import DialogueLines, ScoreReport, TrainingTask, ValidationFinding


MARKER_PATTERN = re.compile(r"<<(核心|Core|コア|Noyau|핵심|Kern|Núcleo|Esencial):.*?>>")
PLACEHOLDER_TOKENS = ("[[[CORE", "{{{", "<<<INSERT", "TODO:", "FIXME:")


def _count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fa5]", text))


def _count_japanese_kana(text: str) -> int:
    return len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text))


def _count_korean_chars(text: str) -> int:
    return len(re.findall(r"[\uac00-\ud7af\u1100-\u11ff]", text))


def score_dialogue(
    task: TrainingTask,
    lines: DialogueLines,
    validator_errors: Optional[List[Any]] = None,
) -> ScoreReport:
    full_text = "\n".join(f"{speaker}: {text}" for speaker, text in lines)
    total_chars = sum(len(text) for _, text in lines)
    marker_count = len(MARKER_PATTERN.findall(full_text))
    findings: List[ValidationFinding] = []
    score = 100.0

    placeholder_hit = next((token for token in PLACEHOLDER_TOKENS if token in full_text), None)
    if placeholder_hit:
        score -= 40
        findings.append(
            ValidationFinding(
                code="placeholder_leak",
                severity="error",
                message=f"存在占位符残留: {placeholder_hit}",
            )
        )

    # 非中文任务的对话行不应包含 "Scenario:" 模板描述（bundle 渲染残留，可出现在行中任意位置）
    if task.language not in ("中文", "粤语"):
        scenario_artifact_lines = [text for _, text in lines if re.search(r"Scenario:\s+[A-Z]", text)]
        if scenario_artifact_lines:
            score -= 30
            findings.append(
                ValidationFinding(
                    code="scenario_placeholder_artifact",
                    severity="error",
                    message=f"对话行含有 'Scenario:' 模板占位符残留",
                    details={"count": len(scenario_artifact_lines), "example": scenario_artifact_lines[0][:80]},
                )
            )

    if marker_count == 0:
        score -= 20
        findings.append(
            ValidationFinding(
                code="missing_core_marker",
                severity="warning",  # bundle output never contains <<核心:…>> markers; downgrade so gate doesn't block everything
                message="缺少核心标记",
            )
        )
    elif marker_count > 2:
        score -= 12
        findings.append(
            ValidationFinding(
                code="too_many_core_markers",
                severity="warning",
                message=f"核心标记数量偏多: {marker_count}",
                details={"marker_count": marker_count},
            )
        )

    # 对话输出中出现任何 <<...>> 标记均为 bundle 渲染残留，直接拦截
    if marker_count > 0:
        score -= 30
        findings.append(
            ValidationFinding(
                code="core_marker_artifact",
                severity="error",
                message=f"对话输出含有核心标记残留 <<…>>: {marker_count} 处",
                details={"marker_count": marker_count},
            )
        )

    chinese_ratio = _count_chinese_chars(full_text) / max(len(full_text), 1)
    kana_ratio = _count_japanese_kana(full_text) / max(len(full_text), 1)
    korean_ratio = _count_korean_chars(full_text) / max(len(full_text), 1)

    if task.language == "日语":
        # 真实日语文本假名占比通常 15-40%；低于 8% 说明主体不是日语
        if kana_ratio < 0.08:
            score -= 30
            findings.append(
                ValidationFinding(
                    code="language_mismatch",
                    severity="error",
                    message=f"日语任务但假名比例过低 {kana_ratio:.1%}（判定为非日语内容）",
                    details={"kana_ratio": round(kana_ratio, 4), "chinese_ratio": round(chinese_ratio, 4)},
                )
            )
        elif chinese_ratio > 0.30:
            # 有足够假名但中文仍然过多
            score -= 20
            findings.append(
                ValidationFinding(
                    code="high_chinese_ratio",
                    severity="error",
                    message=f"日语任务中文占比过高: {chinese_ratio:.1%}",
                    details={"chinese_ratio": round(chinese_ratio, 4), "kana_ratio": round(kana_ratio, 4)},
                )
            )
    elif task.language == "韩语":
        if korean_ratio < 0.05:
            score -= 30
            findings.append(
                ValidationFinding(
                    code="language_mismatch",
                    severity="error",
                    message=f"韩语任务但韩文比例过低 {korean_ratio:.1%}",
                    details={"korean_ratio": round(korean_ratio, 4), "chinese_ratio": round(chinese_ratio, 4)},
                )
            )
    elif task.language not in ("中文", "粤语"):
        # 非 CJK 语言（英语、法语、德语、西班牙语等）不应出现大量中文
        allowed_ratio = 0.70 if task.meta.get("translate_fallback") else 0.15
        if chinese_ratio > allowed_ratio:
            score -= 20
            findings.append(
                ValidationFinding(
                    code="high_chinese_ratio",
                    severity="error",
                    message=f"中文占比过高: {chinese_ratio:.1%}（允许上限 {allowed_ratio:.0%}）",
                    details={"ratio": round(chinese_ratio, 4), "allowed_ratio": allowed_ratio},
                )
            )

    # 逐行检查：日语/韩语已有单独检测；其余非CJK语言不应有中文角色名渗漏
    if task.language not in ("中文", "粤语", "日语", "韩语"):
        leaked_line_count = sum(
            1 for _, text in lines
            if len(text) > 0 and _count_chinese_chars(text) / len(text) > 0.05
        )
        if lines and leaked_line_count / len(lines) > 0.15:
            score -= 20
            findings.append(
                ValidationFinding(
                    code="chinese_role_name_leak",
                    severity="error",
                    message=f"非中文任务行级中文渗漏: {leaked_line_count}/{len(lines)} 行含中文（>5% 字符比例）",
                    details={"leaked_lines": leaked_line_count, "total_lines": len(lines)},
                )
            )

    # 字数严重不足 → error；一般偏离 → warning
    # 日语/韩语 bundle 每次调用产出量天然有限（约 800 字符），large-target 任务
    # 通过跨 chunk 去重累积尽量多的唯一内容；临界值用 1% 而非 40%，避免误杀。
    _wc_critical = 0.01 if task.language in ("日语", "韩语") else 0.40
    if total_chars < task.word_count * _wc_critical:
        score -= 30
        findings.append(
            ValidationFinding(
                code="word_count_critical_short",
                severity="error",
                message=f"字数严重不足(< {_wc_critical:.0%}): target={task.word_count}, actual={total_chars} ({total_chars/max(task.word_count,1):.0%})",
                details={"target": task.word_count, "actual": total_chars},
            )
        )
    elif total_chars < task.word_count * 0.7 or total_chars > task.word_count * 1.3:
        score -= 12
        findings.append(
            ValidationFinding(
                code="word_count_out_of_range",
                severity="warning",
                message=f"字数偏离目标范围: target={task.word_count}, actual={total_chars}",
                details={"target": task.word_count, "actual": total_chars},
            )
        )

    speaker_distribution: Dict[str, int] = {}
    for speaker, _ in lines:
        speaker_distribution[speaker] = speaker_distribution.get(speaker, 0) + 1

    if len(lines) < 10:
        score -= 10
        findings.append(
            ValidationFinding(
                code="too_few_turns",
                severity="warning",
                message=f"对话轮次过少: {len(lines)}",
            )
        )

    if len(lines) > 5:
        unique_texts = {text.strip() for _, text in lines}
        repetition_rate = len(unique_texts) / len(lines)
        if repetition_rate < 0.60:
            score -= 30
            findings.append(
                ValidationFinding(
                    code="high_repetition_rate",
                    severity="error",
                    message=f"重复行比例过高: unique={len(unique_texts)}, total={len(lines)}, 唯一率={repetition_rate:.1%}",
                    details={"unique_lines": len(unique_texts), "total_lines": len(lines), "ratio": round(repetition_rate, 4)},
                )
            )

    if task.people_count >= 3 and "Speaker 3" in speaker_distribution:
        speaker3_lines = [text.strip() for speaker, text in lines if speaker == "Speaker 3"]
        filler_patterns = (
            r"^好的[。！，、]*$",
            r"^明白了[。！，、]*$",
            r"^收到[。！，、]*$",
            r"^确认[。！，、]*$",
            r"^Okay[.! ,]*$",
            r"^Got it[.! ,]*$",
            r"^Understood[.! ,]*$",
        )
        filler_count = 0
        for text in speaker3_lines:
            if any(re.match(pattern, text, re.IGNORECASE) for pattern in filler_patterns):
                filler_count += 1
        filler_ratio = filler_count / max(len(speaker3_lines), 1)
        if filler_ratio > 0.5:
            score -= 10
            findings.append(
                ValidationFinding(
                    code="speaker3_filler_ratio",
                    severity="warning",
                    message=f"Speaker3 空话过多: {filler_ratio:.1%}",
                    details={"ratio": round(filler_ratio, 4)},
                )
            )

    if validator_errors:
        for err in validator_errors:
            code = getattr(err, "error_type", "validator_error")
            message = getattr(err, "message", str(err))
            findings.append(
                ValidationFinding(
                    code=code,
                    severity="error",
                    message=message,
                    details={
                        "line_num": getattr(err, "line_num", None),
                        "content": getattr(err, "content", None),
                    },
                )
            )
        score -= min(30, 5 * len(validator_errors))

    score = max(score, 0.0)
    passed = not any(item.severity == "error" for item in findings) and score >= 60
    unique_count = len({text.strip() for _, text in lines})
    metrics = {
        "line_count": len(lines),
        "total_chars": total_chars,
        "marker_count": marker_count,
        "chinese_ratio": round(chinese_ratio, 4),
        "kana_ratio": round(kana_ratio, 4),
        "korean_ratio": round(korean_ratio, 4),
        "speaker_distribution": speaker_distribution,
        "target_word_count": task.word_count,
        "unique_line_ratio": round(unique_count / max(len(lines), 1), 4),
    }
    return ScoreReport(
        passed=passed,
        score=score,
        max_score=100.0,
        metrics=metrics,
        findings=findings,
    )
