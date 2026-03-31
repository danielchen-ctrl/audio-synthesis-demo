from __future__ import annotations

import random
import re
from typing import Any

from demo_app.rule_loader import load_text_naturalness_rules


LANGUAGE_ALIASES = {
    "中文": "Chinese",
    "中文（普通话）": "Chinese",
    "Chinese": "Chinese",
    "英语": "English",
    "英文": "English",
    "English": "English",
    "日语": "Japanese",
    "日本語": "Japanese",
    "Japanese": "Japanese",
    "韩语": "Korean",
    "한국어": "Korean",
    "Korean": "Korean",
    "法语": "French",
    "French": "French",
    "德语": "German",
    "Deutsch": "German",
    "German": "German",
    "西班牙语": "Spanish",
    "Español": "Spanish",
    "Spanish": "Spanish",
    "葡萄牙语": "Portuguese",
    "Português": "Portuguese",
    "Portuguese": "Portuguese",
    "粤语": "Cantonese",
    "Cantonese": "Cantonese",
}

_PLACEHOLDER_ROLE_RE = re.compile(
    r"(Professional|Counterpart|Coordinator|Participant|Consultant|Third\s*Party)",
    flags=re.IGNORECASE,
)
_CORE_MARKER_RE = re.compile(r"<<\s*(?:Core|核心)\s*:\s*(.+?)\s*>>", flags=re.IGNORECASE)
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z]{4,}")
_RISK_ALERT_RE = re.compile(r"risk\s*alert", flags=re.IGNORECASE)

_DOCTOR_NAME_POOL = ["李医生", "王医生", "陈医生", "周医生", "赵医生", "吴医生", "孙医生", "刘医生"]
_PATIENT_NAME_POOL = ["张阿姨", "王阿姨", "刘叔叔", "赵先生", "李女士", "陈大爷", "周女士", "孙先生"]
_BUSINESS_NAME_POOL = ["李明", "王芳", "张伟", "刘洋", "陈静", "赵磊", "周婷", "孙杰", "吴敏", "郑凯"]

_CN_TEMPLATE_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^从实际情况来看，这个方案需要分几个步骤.*"), "如果要继续推进，最好先把现状摸清，再决定方案和节奏。"),
    (re.compile(r"^根据以往的经验，类似的情况处理周期.*"), "如果按常规节奏推进，一般要先确认现状，再安排后续处理，不用急着一步到位。"),
    (re.compile(r"^基于刚才的讨论，我建议我们有几个选择[:：]?$"), "现在大致有两种思路，我们可以一起权衡哪种更合适。"),
    (re.compile(r"^方案1[:：].*"), "一种做法是先从最关键的部分开始，边推进边看效果。"),
    (re.compile(r"^方案2[:：].*"), "另一种做法是先把方案准备充分，再整体往下推。"),
    (re.compile(r"^在做出决定之前，我需要提醒您几个重要的注意事项[:：]?$"), "在定下来之前，有几个现实问题要先想清楚。"),
    (re.compile(r"^需要提醒您的是，这个方案可能需要一些额外的时间和资源.*"), "不过这件事确实要多花一点时间和精力，前面最好先留出余量。"),
    (re.compile(r"^实施过程中可能会遇到一些意外情况.*"), "推进过程中难免会有变动，我们到时及时沟通调整就行。"),
    (re.compile(r"^好的，让我们总结一下[:：]?$"), "那我简单收一下重点。"),
    (re.compile(r"^我建议我们先制定一个详细的时间表.*"), "下一步可以先把节奏和分工对一遍，这样后面会顺很多。"),
    (re.compile(r"^下周我们可以再开一次会.*"), "等我们把这轮情况捋顺，再约个时间把后面的安排定下来。"),
    (re.compile(r"^我建议我们下周再安排一次详细讨论.*"), "后面再约一次时间，把具体安排往下敲定。"),
]


def canonical_language(value: str | None) -> str:
    text = str(value or "").strip()
    return LANGUAGE_ALIASES.get(text, text or "Chinese")


def _normalize_line_text(text: str) -> str:
    updated = re.sub(r"\s+", " ", str(text or "").strip())
    updated = re.sub(r"\s+([,.!?;:])", r"\1", updated)
    return updated


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _ascii_ratio(text: str) -> float:
    compact = [ch for ch in text if not ch.isspace()]
    if not compact:
        return 0.0
    ascii_count = sum(1 for ch in compact if ord(ch) < 128)
    return ascii_count / len(compact)


def _speaker_order(lines: list[tuple[str, str]]) -> list[str]:
    order: list[str] = []
    for speaker, _ in lines:
        if speaker not in order:
            order.append(speaker)
    return order


def _clip_text(text: str, limit: int = 18) -> str:
    cleaned = re.sub(r"\s+", "", str(text or ""))
    cleaned = cleaned.replace("<<", "").replace(">>", "")
    cleaned = re.sub(r"[：:;；，,。.!?？“”\"'<>（）()\[\]]", "", cleaned)
    return cleaned[:limit] if len(cleaned) > limit else cleaned


def _context_topic_fragment(scenario: str, core_content: str, profile: dict[str, Any] | None) -> str:
    candidates = [
        str(scenario or "").strip(),
        str((profile or {}).get("work_content") or "").strip(),
        str((profile or {}).get("use_case") or "").strip(),
        str(core_content or "").strip(),
    ]
    for candidate in candidates:
        if candidate and _contains_cjk(candidate):
            fragment = _clip_text(candidate, 20)
            if fragment:
                return fragment
    return "这件事"


def _core_focus_fragment(core_content: str, scenario: str) -> str:
    for candidate in (core_content, scenario):
        text = str(candidate or "").strip()
        if text and _contains_cjk(text):
            return _clip_text(text, 24)
    return ""


def _is_medical_context(scenario: str, core_content: str, profile: dict[str, Any] | None) -> bool:
    combined = " ".join(
        part
        for part in [
            str(scenario or ""),
            str(core_content or ""),
            str((profile or {}).get("job_function") or ""),
            str((profile or {}).get("work_content") or ""),
            str((profile or {}).get("use_case") or ""),
        ]
        if part
    )
    keywords = ["医生", "病人", "患者", "病情", "治疗", "复查", "问诊", "门诊", "症状", "癌", "肿瘤", "内科"]
    return any(keyword in combined for keyword in keywords)


def _pick_unique_name(pool: list[str], used: set[str], rng: random.Random) -> str:
    available = [name for name in pool if name not in used] or pool
    chosen = rng.choice(available)
    used.add(chosen)
    return chosen


def _build_chinese_speaker_names(
    lines: list[tuple[str, str]],
    scenario: str,
    core_content: str,
    profile: dict[str, Any] | None,
) -> dict[str, str]:
    order = _speaker_order(lines)
    if not order:
        return {}

    rng = random.Random(random.SystemRandom().randrange(1, 2**32))
    medical = _is_medical_context(scenario, core_content, profile)
    used: set[str] = set()
    mapping: dict[str, str] = {}

    for index, speaker in enumerate(order):
        if medical and index == 0:
            pool = _DOCTOR_NAME_POOL
        elif medical:
            pool = _PATIENT_NAME_POOL
        else:
            pool = _BUSINESS_NAME_POOL
        mapping[speaker] = _pick_unique_name(pool, used, rng)
    return mapping


def _build_intro_line(
    speaker: str,
    primary_speaker: str,
    speaker_names: dict[str, str],
    topic: str,
    medical: bool,
) -> str:
    name = speaker_names.get(speaker, "李明")
    if speaker == primary_speaker:
        if medical:
            return f"你好，我是{name}，先跟你一起把{topic}梳理清楚。"
        if topic == "这件事":
            return f"你好，我是{name}，我们先把这件事聊明白。"
        return f"你好，我是{name}，我们先把{topic}聊明白。"
    if medical:
        return f"你好，我是{name}，我主要想了解一下{topic}现在该怎么处理。"
    return f"你好，我是{name}，我先把这边最关心的情况说具体一点。"


def _build_core_line(speaker: str, primary_speaker: str, focus: str) -> str:
    if speaker == primary_speaker:
        if focus == "这件事":
            return "我先说重点，这件事要讲透，很多判断都卡在这里。"
        return f"我先说重点，{focus}这部分要讲透，很多判断都卡在这里。"
    return f"我现在最关心的还是{focus}，想听听更具体的建议。"


def _generic_chinese_fallback(speaker: str, primary_speaker: str, topic: str, medical: bool) -> str:
    if speaker == primary_speaker:
        return f"先别急着下结论，我们把{topic}相关的情况一条一条过一下。"
    if medical:
        return f"好，那我把和{topic}有关的实际感受再说具体一点。"
    return f"好，我把和{topic}有关的顾虑再讲清楚一点。"


def _rewrite_chinese_line(
    speaker: str,
    raw_text: str,
    primary_speaker: str,
    speaker_names: dict[str, str],
    topic: str,
    focus: str,
    medical: bool,
) -> str:
    original = _normalize_line_text(raw_text)
    if not original:
        return ""

    if _PLACEHOLDER_ROLE_RE.search(original):
        return _build_intro_line(speaker, primary_speaker, speaker_names, topic, medical)

    if _CORE_MARKER_RE.search(original) or original.lower().startswith("the most important thing is"):
        return _build_core_line(speaker, primary_speaker, focus or topic)

    if _RISK_ALERT_RE.search(original):
        return f"还有一点要提前注意，{topic}往下推进时的风险和节奏也要盯紧。"

    updated = original
    for pattern, replacement in _CN_TEMPLATE_REWRITES:
        if pattern.match(updated):
            updated = replacement
            break

    if _PLACEHOLDER_ROLE_RE.search(updated):
        updated = _build_intro_line(speaker, primary_speaker, speaker_names, topic, medical)

    if _CORE_MARKER_RE.search(updated):
        updated = _build_core_line(speaker, primary_speaker, focus or topic)

    if _ascii_ratio(updated) > 0.42 and not _contains_cjk(updated):
        updated = _generic_chinese_fallback(speaker, primary_speaker, topic, medical)
    elif _ascii_ratio(updated) > 0.42 and _ASCII_TOKEN_RE.search(updated):
        updated = _generic_chinese_fallback(speaker, primary_speaker, topic, medical)

    return _normalize_line_text(updated.replace("<<", "").replace(">>", ""))


def _polish_chinese_generated_lines(
    lines: list[tuple[str, str]],
    scenario: str,
    core_content: str,
    profile: dict[str, Any] | None,
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    if not lines:
        return [], {"language": "Chinese", "rewrite_count": 0, "rewrites": []}

    topic = _context_topic_fragment(scenario, core_content, profile)
    focus = _core_focus_fragment(core_content, scenario) or topic
    medical = _is_medical_context(scenario, core_content, profile)
    speaker_names = _build_chinese_speaker_names(lines, scenario, core_content, profile)
    primary_speaker = _speaker_order(lines)[0]

    rewritten: list[tuple[str, str]] = []
    rewrite_meta: list[dict[str, str]] = []

    for speaker, raw_text in lines:
        original = _normalize_line_text(raw_text)
        updated = _rewrite_chinese_line(speaker, raw_text, primary_speaker, speaker_names, topic, focus, medical)
        if not updated:
            continue
        if rewritten and rewritten[-1][1] == updated:
            continue
        rewritten.append((speaker, updated))
        if updated != original:
            rewrite_meta.append({"speaker": speaker, "before": original, "after": updated})

    if not rewritten:
        fallback = _generic_chinese_fallback(primary_speaker, primary_speaker, topic, medical)
        rewritten = [(primary_speaker, fallback)]
        rewrite_meta.append({"speaker": primary_speaker, "before": "", "after": fallback})

    return rewritten, {
        "language": "Chinese",
        "rewrite_count": len(rewrite_meta),
        "rewrites": rewrite_meta,
        "speaker_names": speaker_names,
    }


def enforce_keywords_in_lines(
    lines: list[tuple[str, str]],
    keywords: list[str],
    language: str,
    *,
    scenario: str = "",
    core_content: str = "",
    profile: dict[str, Any] | None = None,
) -> tuple[list[tuple[str, str]], list[str]]:
    normalized_keywords = [item.strip() for item in keywords if item and item.strip()]
    if not normalized_keywords:
        return list(lines), []

    rendered_text = "\n".join(f"{speaker}: {content}" for speaker, content in lines)
    missing_keywords = [keyword for keyword in normalized_keywords if keyword.casefold() not in rendered_text.casefold()]
    if not missing_keywords:
        return list(lines), []

    order = _speaker_order(lines) or ["Speaker 1"]
    primary_speaker = order[0]
    topic = _context_topic_fragment(scenario, core_content, profile)
    canonical = canonical_language(language)

    if canonical == "Chinese":
        additions: list[tuple[str, str]] = []
        for index in range(0, len(missing_keywords), 2):
            chunk = missing_keywords[index:index + 2]
            speaker = order[(index // 2 + 1) % len(order)] if len(order) > 1 else primary_speaker
            joined = "、".join(chunk)
            if speaker == primary_speaker:
                content = f"另外，围绕{topic}这件事，{joined}这块也得重点说清楚。"
            else:
                content = f"对，我现在最关心的就是{joined}，想听听你更具体的判断。"
            additions.append((speaker, content))
        return [*lines, *additions], missing_keywords

    speaker_label = primary_speaker
    appended_text = f"We should explicitly cover these keywords in the dialogue: {', '.join(missing_keywords)}."
    return [*lines, (speaker_label, appended_text)], missing_keywords


def polish_generated_lines(
    lines: list[tuple[str, str]],
    language: str,
    *,
    scenario: str = "",
    core_content: str = "",
    profile: dict[str, Any] | None = None,
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    canonical = canonical_language(language)
    if canonical == "Chinese":
        return _polish_chinese_generated_lines(lines, scenario, core_content, profile)
    if canonical in {"", "English"}:
        return list(lines), {"language": canonical, "rewrite_count": 0, "rewrites": []}

    rules = load_text_naturalness_rules().get("languages", {}).get(canonical, {})
    if not isinstance(rules, dict):
        return list(lines), {"language": canonical, "rewrite_count": 0, "rewrites": []}

    exact_replacements = rules.get("exact_replacements") or {}
    speaker_variants = rules.get("speaker_variants") or {}
    regex_replacements = rules.get("regex_replacements") or []

    rewritten: list[tuple[str, str]] = []
    rewrite_meta: list[dict[str, str]] = []

    for speaker, raw_text in lines:
        original = _normalize_line_text(raw_text)
        updated = original

        variants = speaker_variants.get(original)
        if isinstance(variants, dict):
            updated = variants.get(speaker, variants.get("default", updated))

        if updated == original and original in exact_replacements:
            updated = exact_replacements[original]

        for item in regex_replacements:
            if not isinstance(item, dict):
                continue
            pattern = item.get("pattern")
            replace = item.get("replace", "")
            allowed_speaker = item.get("speaker")
            allowed_speakers = item.get("speakers")
            if not pattern:
                continue
            if allowed_speaker and allowed_speaker != speaker:
                continue
            if isinstance(allowed_speakers, list) and speaker not in allowed_speakers:
                continue
            updated = re.sub(pattern, replace, updated)

        updated = _normalize_line_text(updated)
        rewritten.append((speaker, updated))
        if updated != original:
            rewrite_meta.append({"speaker": speaker, "before": original, "after": updated})

    return rewritten, {
        "language": canonical,
        "rewrite_count": len(rewrite_meta),
        "rewrites": rewrite_meta,
    }
