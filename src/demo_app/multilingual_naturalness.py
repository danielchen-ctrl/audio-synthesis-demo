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


def _keyword_in_text(text: str, keyword: str) -> bool:
    return str(keyword or "").casefold() in str(text or "").casefold()


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


def _normalize_topic_candidate(text: str, limit: int = 20) -> str:
    updated = str(text or "").strip()
    if not updated:
        return ""
    updated = re.sub(r"^(文本主题|主题|场景|主题概括)\s*[:：]?\s*", "", updated)
    updated = re.sub(r"^(围绕|关于)", "", updated)
    updated = re.sub(r"(进行真实自然的多轮.*|展开真实自然的多轮.*|多轮.*对话|场景对话|评审会对话|进行讨论|展开讨论)$", "", updated)
    updated = re.sub(r"\s+", "", updated)
    updated = updated.strip("“”\"'《》[]【】")
    if not updated:
        return ""
    return updated[:limit] if len(updated) > limit else updated


def _split_meaningful_pieces(text: str) -> list[str]:
    updated = str(text or "").strip()
    if not updated:
        return []
    updated = re.sub(r"^(核心对话内容|核心内容|补充要求|文本主题|主题模板|行业场景|场景类型|角色分工|讨论重点|目标输出|写作要求|参与角色|最终目标|主题)\s*[:：]?\s*", "", updated)
    updated = re.sub(r"对话中必须明确体现这些关键词[——:：-]*", "", updated)
    updated = re.sub(r"(请生成自然、真实、口语化的多轮对话文本|请生成真实自然的多轮对话文本)", "", updated)
    pieces: list[str] = []
    for piece in re.split(r"[\n,，。；;、/｜|]+", updated):
        piece = re.sub(r"^(核心对话内容|核心内容|补充要求|文本主题|主题模板|行业场景|场景类型|角色分工|讨论重点|目标输出|写作要求|参与角色|最终目标|主题)\s*[:：]?\s*", "", piece.strip())
        cleaned = _normalize_topic_candidate(piece, limit=24)
        if cleaned and cleaned not in pieces:
            pieces.append(cleaned)
    return pieces


def _context_topic_fragment(title: str, scenario: str, core_content: str, profile: dict[str, Any] | None) -> str:
    candidates = [
        str(title or "").strip(),
        str((profile or {}).get("work_content") or "").strip(),
        str(scenario or "").strip(),
        str((profile or {}).get("use_case") or "").strip(),
        str(core_content or "").strip(),
    ]
    for candidate in candidates:
        if candidate and _contains_cjk(candidate):
            fragment = _normalize_topic_candidate(candidate, 20)
            if fragment and fragment not in {"在线生成音频", "这件事"}:
                return fragment
    return "这件事"


def _core_focus_fragment(title: str, core_content: str, scenario: str, profile: dict[str, Any] | None) -> str:
    for candidate in (core_content, title, str((profile or {}).get("work_content") or ""), scenario):
        pieces = _split_meaningful_pieces(candidate)
        if pieces:
            return pieces[0]
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
    role_hint: str = "",
    scene_goal: str = "",
) -> str:
    name = speaker_names.get(speaker, "李明")
    if speaker == primary_speaker:
        if role_hint:
            role_prefix = f"，我这边是{role_hint}" if re.search(r"(负责人|经理|医生|主管|代表)$", role_hint) else f"，我主要负责{role_hint}"
        else:
            role_prefix = ""
        if medical:
            return f"你好，我是{name}{role_prefix}，先跟你一起把{topic}梳理清楚。"
        if topic == "这件事":
            return f"你好，我是{name}{role_prefix}，我们先把这件事聊明白。"
        return f"你好，我是{name}{role_prefix}，我们先把{topic}聊明白。"
    role_prefix = f"，我主要站在{role_hint}这个角度" if role_hint else ""
    if medical:
        return f"你好，我是{name}{role_prefix}，我主要想了解一下{topic}现在该怎么处理。"
    goal_suffix = f"，尤其想把{scene_goal}里我最担心的部分说具体" if scene_goal and len(scene_goal) < 40 else ""
    return f"你好，我是{name}{role_prefix}，我先把这边最关心的情况说具体一点{goal_suffix}。"


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
    *,
    title: str = "",
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    if not lines:
        return [], {"language": "Chinese", "rewrite_count": 0, "rewrites": []}

    topic = _context_topic_fragment(title, scenario, core_content, profile)
    focus = _core_focus_fragment(title, core_content, scenario, profile) or topic
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
    title: str = "",
    scenario: str = "",
    core_content: str = "",
    profile: dict[str, Any] | None = None,
    generation_context: dict[str, Any] | None = None,
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
    topic = _context_topic_fragment(title, scenario, core_content, profile)
    canonical = canonical_language(language)

    if canonical == "Chinese":
        updated = list(lines)
        additions: list[tuple[str, str]] = []
        role_briefs = _context_role_briefs(generation_context, profile, len(order), _is_medical_context(scenario, core_content, profile))
        for index, keyword in enumerate(missing_keywords):
            speaker = order[(index + 1) % len(order)] if len(order) > 1 else primary_speaker
            injected = False
            for pos in range(len(updated) - 1, -1, -1):
                line_speaker, line_text = updated[pos]
                if line_speaker != speaker or _keyword_in_text(line_text, keyword):
                    continue
                clause = (
                    f"尤其是{keyword}这块需要单独盯住"
                    if speaker == primary_speaker
                    else f"我这里最担心的就是{keyword}会不会影响后面的判断"
                )
                updated[pos] = (line_speaker, _normalize_line_text(f"{line_text.rstrip('。！？!?；;，,')}，{clause}。"))
                injected = True
                break
            if injected:
                continue
            joined_role = role_briefs[order.index(speaker)] if speaker in order and order.index(speaker) < len(role_briefs) else "相关角色"
            if speaker == primary_speaker:
                additions.append((speaker, f"另外，围绕{topic}这件事，{keyword}这块也得重点说清楚。"))
            else:
                additions.append((speaker, f"从{joined_role}这边看，我现在最关心的就是{keyword}，想听听更具体的判断。"))
        return [*updated, *additions], missing_keywords

    speaker_label = primary_speaker
    appended_text = f"We should explicitly cover these keywords in the dialogue: {', '.join(missing_keywords)}."
    return [*lines, (speaker_label, appended_text)], missing_keywords


def polish_generated_lines(
    lines: list[tuple[str, str]],
    language: str,
    *,
    title: str = "",
    scenario: str = "",
    core_content: str = "",
    profile: dict[str, Any] | None = None,
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    canonical = canonical_language(language)
    if canonical == "Chinese":
        return _polish_chinese_generated_lines(lines, scenario, core_content, profile, title=title)
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


_GENERIC_SECONDARY_PATTERNS = [
    re.compile(r"^这个我需要回去确认一下"),
    re.compile(r"^我会认真思考这个问题"),
    re.compile(r"^这确实需要我进一步研究"),
    re.compile(r"^这个方案听起来不错"),
    re.compile(r"^我明白了，这个确实需要注意"),
    re.compile(r"^好的，我理解了"),
]

_SECONDARY_ROLE_HINTS = [
    "现状和问题",
    "技术与执行风险",
    "时间和资源约束",
    "用户体验和反馈",
    "数据指标和验证",
    "协作分工和落地",
    "外部依赖和配合",
    "上线节奏和回滚",
    "培训和宣导",
]

_BUSINESS_FOCUS_DEFAULTS = [
    "当前现状",
    "主要阻塞",
    "责任分工",
    "验收标准",
    "资源排期",
    "上线窗口",
    "回滚预案",
    "数据验证",
]

_MEDICAL_FOCUS_DEFAULTS = [
    "当前症状",
    "检查结果",
    "治疗安排",
    "复查节点",
    "风险提示",
    "用药配合",
    "家属协助",
]

_DOMAIN_ROLE_HINTS = {
    "医疗健康": ["随访医生", "患者本人", "家属", "随访护士"],
    "人力资源与招聘": ["招聘负责人", "业务部门经理", "HRBP", "用人主管"],
    "娱乐/媒体": ["业务负责人", "经纪人", "商务负责人", "内容运营"],
    "建筑与工程行业": ["项目经理", "工程负责人", "甲方代表", "成本负责人"],
    "汽车行业": ["车型项目负责人", "市场负责人", "销售负责人", "区域运营"],
    "咨询/专业服务": ["客户拓展负责人", "顾问经理", "行业顾问", "交付负责人"],
    "法律服务": ["法务负责人", "客户负责人", "专项律师", "合规经理"],
    "金融/投资": ["投顾负责人", "客户经理", "研究员", "风险控制负责人"],
    "零售行业": ["会员运营负责人", "门店负责人", "活动运营", "数据分析师"],
    "保险行业": ["销售管理负责人", "培训负责人", "质检负责人", "数据分析师"],
    "房地产": ["项目营销负责人", "渠道经理", "案场负责人", "投放运营"],
    "人工智能/科技": ["增长负责人", "产品经理", "数据分析师", "运营负责人"],
    "制造业": ["产线负责人", "工艺工程师", "设备负责人", "质量经理"],
    "测试开发": ["测试负责人", "服务端开发", "客户端开发", "产品经理", "质量负责人"],
}


def _content_length(lines: list[tuple[str, str]]) -> int:
    return sum(len(re.sub(r"\s+", "", str(text or ""))) for _, text in lines)


def _normalize_generation_context(generation_context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(generation_context, dict):
        return {}
    role_briefs = [
        str(item or "").strip()
        for item in generation_context.get("role_briefs", [])
        if str(item or "").strip()
    ]
    discussion_axes = [
        str(item or "").strip()
        for item in generation_context.get("discussion_axes", [])
        if str(item or "").strip()
    ]
    quality_constraints = [
        str(item or "").strip()
        for item in generation_context.get("quality_constraints", [])
        if str(item or "").strip()
    ]
    return {
        "domain": str(generation_context.get("domain") or "").strip(),
        "scene_type": str(generation_context.get("scene_type") or "").strip(),
        "scene_goal": str(generation_context.get("scene_goal") or "").strip(),
        "deliverable": str(generation_context.get("deliverable") or "").strip(),
        "role_briefs": role_briefs,
        "discussion_axes": discussion_axes,
        "quality_constraints": quality_constraints,
    }


def _context_role_briefs(
    generation_context: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    people_count: int,
    medical: bool,
) -> list[str]:
    context = _normalize_generation_context(generation_context)
    roles = [item for item in context.get("role_briefs", []) if item]
    if not roles:
        domain = str(context.get("domain") or "").strip()
        if not domain:
            use_case = str((profile or {}).get("use_case") or "")
            if "｜" in use_case:
                domain = use_case.split("｜", 1)[0].strip()
        roles = list(_DOMAIN_ROLE_HINTS.get(domain, []))
    if not roles:
        roles = ["接诊医生", "患者本人", "家属"] if medical else ["负责人", *_SECONDARY_ROLE_HINTS]

    while len(roles) < people_count:
        roles.append(f"相关协作方{len(roles)}")
    return roles[:people_count]


def _rendered_length(lines: list[tuple[str, str]]) -> int:
    return len("\n".join(f"{speaker}: {text}" for speaker, text in lines))


def _speaker_turn_counts(lines: list[tuple[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for speaker, _ in lines:
        counts[speaker] = counts.get(speaker, 0) + 1
    return counts


def _split_focus_candidates(*values: str) -> list[str]:
    results: list[str] = []
    for value in values:
        for piece in _split_meaningful_pieces(value):
            cleaned = _normalize_topic_candidate(piece, 22)
            if cleaned and cleaned not in results and len(cleaned) >= 2:
                results.append(cleaned)
    return results


def _secondary_line_is_generic(text: str) -> bool:
    normalized = _normalize_line_text(text)
    if len(normalized) < 12:
        return True
    return any(pattern.search(normalized) for pattern in _GENERIC_SECONDARY_PATTERNS)


def _needs_dialogue_repair(
    lines: list[tuple[str, str]],
    people_count: int,
    target_word_count: int,
) -> bool:
    if not lines:
        return True

    order = _speaker_order(lines)
    if len(order) != people_count:
        return True

    counts = _speaker_turn_counts(lines)
    for speaker in order[1:]:
        if counts.get(speaker, 0) < 2:
            return True

    rendered = [_normalize_line_text(text) for _, text in lines if _normalize_line_text(text)]
    if not rendered:
        return True

    unique_ratio = len(set(rendered)) / max(1, len(rendered))
    if unique_ratio < 0.75:
        return True

    generic_secondary = sum(1 for speaker, text in lines if speaker != order[0] and _secondary_line_is_generic(text))
    if generic_secondary >= max(2, len(order) - 1):
        return True

    if _content_length(lines) < int(target_word_count * 0.92):
        return True

    return False


def _structured_focus_points(
    topic: str,
    focus: str,
    keywords: list[str],
    core_content: str,
    scenario: str,
    medical: bool,
    generation_context: dict[str, Any] | None = None,
) -> list[str]:
    preferred = [item.strip() for item in keywords if item and item.strip()]
    context = _normalize_generation_context(generation_context)
    context_axes = context.get("discussion_axes", [])
    candidates = [*preferred, *context_axes, *_split_focus_candidates(focus, core_content, topic)]
    if not context_axes:
        candidates.extend(_split_focus_candidates(scenario))
    ignored = {str(context.get("domain") or "").strip(), "测试开发", "通用业务"}
    deliverable = context.get("deliverable")
    if deliverable:
        candidates.extend(_split_focus_candidates(str(deliverable)))
    results: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in ignored and candidate not in results:
            results.append(candidate)
    defaults = _MEDICAL_FOCUS_DEFAULTS if medical else _BUSINESS_FOCUS_DEFAULTS
    for candidate in defaults:
        if candidate not in results:
            results.append(candidate)
    if not results:
        results = [topic or "当前情况"]
    return results


def _speaker_specific_point(points: list[str], speaker_index: int, round_index: int) -> str:
    if not points:
        return "当前情况"
    return points[(speaker_index * 2 + round_index) % len(points)]


def _primary_summary_line(topic: str, focus: str, round_index: int) -> str:
    variants = [
        f"我先把主线收一下，围绕{topic}，目前最关键的还是{focus or topic}这部分。",
        f"听下来，大家担心的点其实很集中，核心都落在{focus or topic}这里。",
        f"如果现在就往下推进，先把{focus or topic}说透，后面的判断才不会跑偏。",
        f"我们先不求一步到位，先围绕{focus or topic}把问题边界、目标和节奏定住。",
    ]
    return variants[round_index % len(variants)]


def _secondary_intro_line(name: str, role_hint: str, point: str, medical: bool) -> str:
    if medical:
        return f"你好，我是{name}，我这边主要想围绕{role_hint}再问清楚一点，尤其是{point}这块。"
    return f"你好，我是{name}，我先从{role_hint}这个角度补充一下，尤其想把{point}这块说具体。"


def _secondary_round_line(
    role_hint: str,
    point: str,
    round_index: int,
    speaker_variant: int,
    medical: bool,
) -> str:
    if medical:
        variants = [
            f"从{role_hint}这边看，我最想先确认的就是{point}，因为这会直接影响后面的治疗安排。",
            f"我再补充一点，关于{point}我现在最担心的是信息不够清楚，怕判断偏了。",
            f"如果围绕{point}来处理，我希望先把接下来要观察什么、多久复查一次说明确。",
            f"另外{point}这块要是没处理好，我会一直担心后面恢复和复诊节奏受影响。",
        ]
    else:
        variants = [
            f"从{role_hint}这边看，我最想先确认的就是{point}，不然很多后续动作都没法稳稳往下走。",
            f"我再补充一点，关于{point}我现在最担心的是边界不够清楚，后面容易反复返工。",
            f"如果围绕{point}继续推进，我希望先把谁来负责、什么时候验证、出什么结果讲明白。",
            f"另外{point}这块一旦处理得太粗，后面无论是执行还是复盘都会比较被动。",
        ]
    return variants[(round_index + speaker_variant) % len(variants)]


def _secondary_followup_line(role_hint: str, point: str, round_index: int, speaker_variant: int, medical: bool) -> str:
    if medical:
        variants = [
            f"如果继续围绕{point}推进，我更想知道后面观察指标、复查节点和可能的风险提示应该怎么安排。",
            f"从{role_hint}的角度，我还想追问一下{point}会不会影响后面的恢复节奏和用药判断。",
            f"那关于{point}，我们是不是要先把检查、复查和家属配合的重点同步好，避免中间理解偏差。",
            f"我担心的是，如果{point}这块讲得不够细，回去以后我自己执行起来还是容易心里没底。",
        ]
    else:
        variants = [
            f"如果继续围绕{point}推进，我更想知道谁来拍板、什么时候验收、出了问题怎么兜底。",
            f"从{role_hint}的角度，我还想追问一下{point}会不会影响上线窗口、资源排期和回滚准备。",
            f"那关于{point}，我们是不是要先把负责人、验证标准和失败后的应对动作一次讲清楚，避免后面扯皮。",
            f"我担心的是，如果{point}这块讲得不够细，团队回去以后各自理解不同，执行就会很散。",
        ]
    return variants[(round_index + speaker_variant) % len(variants)]


def _primary_response_line(point: str, round_index: int, medical: bool) -> str:
    if medical:
        variants = [
            f"你提到的{point}确实要先说清楚，我们先把现状、风险和接下来几步安排捋顺。",
            f"这个点我认可，围绕{point}不能只看表面，要把症状变化、检查结果和后续复查一起考虑。",
            f"那我们就按{point}来拆，先确认当前情况，再决定要不要调整治疗和复查节奏。",
            f"{point}这部分我会讲细一点，关键不是一句结论，而是让你知道为什么这样判断、接下来怎么做。",
        ]
    else:
        variants = [
            f"你提到的{point}确实要先说清楚，我们先把现状、风险和下一步动作对齐。",
            f"这个点我认可，围绕{point}不能只停在判断上，还得把执行条件和校验口径讲透。",
            f"那我们就按{point}来拆，先确认事实，再决定方案优先级和推进节奏。",
            f"{point}这部分我会讲细一点，关键不是喊口号，而是把真正会影响结果的地方说透。",
    ]
    return variants[round_index % len(variants)]


def _primary_plan_line(point: str, topic: str, round_index: int, medical: bool) -> str:
    if medical:
        variants = [
            f"所以围绕{point}，我的建议是先把当前情况说明白，再把复查安排、观察重点和异常处理方式定下来。",
            f"接下来我们就按{topic}这条主线往下走，先确认关键风险，再决定哪些地方需要提前干预。",
            f"你们刚才提到的点我都记住了，后面会围绕{point}把结论、节奏和注意事项说得更落地一些。",
        ]
    else:
        variants = [
            f"所以围绕{point}，我的建议是先把事实、责任人和验收标准定住，再安排后续推进节奏。",
            f"接下来我们就按{topic}这条主线往下走，先收敛关键风险，再决定资源和上线窗口怎么排。",
            f"你们刚才提到的点我都记住了，后面会围绕{point}把动作、边界和兜底方案讲得更落地一些。",
        ]
    return variants[round_index % len(variants)]


def _secondary_commit_line(role_hint: str, point: str, round_index: int, speaker_variant: int, medical: bool) -> str:
    if medical:
        variants = [
            f"明白了，那我会先把和{point}有关的实际感受、检查情况和这段时间的变化整理出来。",
            f"好，那围绕{point}我这边会先按你说的观察，有异常就及时反馈，不拖到下次再说。",
            f"这样我就更清楚了，后面关于{point}我会按你说的节奏配合复查和记录。",
        ]
    else:
        variants = [
            f"明白了，那我这边会先把和{point}有关的现状、数据和阻塞项整理出来，再跟大家对一次。",
            f"好，那围绕{point}我会从{role_hint}这个角度先把责任人、时间点和验证方式补齐，避免后面再来回改。",
            f"这样我就更清楚了，后面关于{point}我会先把和{role_hint}有关的准备工作做扎实，再推进下一步。",
        ]
    return variants[(round_index + speaker_variant) % len(variants)]


def _build_structured_chinese_dialogue(
    lines: list[tuple[str, str]],
    title: str,
    scenario: str,
    core_content: str,
    profile: dict[str, Any] | None,
    target_word_count: int,
    people_count: int,
    keywords: list[str],
    generation_context: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    order = [f"Speaker {index}" for index in range(1, max(2, people_count) + 1)]
    topic = _context_topic_fragment(title, scenario, core_content, profile)
    medical = _is_medical_context(scenario, core_content, profile)
    speaker_names = _build_chinese_speaker_names([(speaker, "") for speaker in order], scenario, core_content, profile)
    focus_seed = _core_focus_fragment(title, core_content, scenario, profile) or topic
    context = _normalize_generation_context(generation_context)
    role_briefs = _context_role_briefs(context, profile, len(order), medical)
    points = _structured_focus_points(topic, focus_seed, keywords, core_content, scenario, medical, context)
    focus = "、".join(points[:2]) if len(points) > 1 else (points[0] if points else topic)

    rebuilt: list[tuple[str, str]] = []
    primary = order[0]
    secondary = order[1:] or [primary]

    for idx, speaker in enumerate(order):
        role_hint = role_briefs[idx] if idx < len(role_briefs) else _SECONDARY_ROLE_HINTS[idx % len(_SECONDARY_ROLE_HINTS)]
        if idx == 0:
            rebuilt.append((speaker, _build_intro_line(speaker, primary, speaker_names, topic, medical, role_hint, context.get("scene_goal", ""))))
            continue
        point = _speaker_specific_point(points, idx - 1, 0)
        rebuilt.append((speaker, _secondary_intro_line(speaker_names.get(speaker, "李明"), role_hint, point, medical)))
    rebuilt.append((primary, _build_core_line(primary, primary, focus)))

    round_index = 0
    target_floor = max(260, int(target_word_count * 0.99))
    max_rounds = max(8, min(14, int(target_word_count / 110)))
    while _content_length(rebuilt) < target_floor:
        for idx, speaker in enumerate(secondary):
            role_hint = role_briefs[idx + 1] if idx + 1 < len(role_briefs) else _SECONDARY_ROLE_HINTS[idx % len(_SECONDARY_ROLE_HINTS)]
            point = _speaker_specific_point(points, idx, round_index)
            rebuilt.append((speaker, _secondary_round_line(role_hint, point, round_index, idx, medical)))
        rebuilt.append((primary, _primary_summary_line(topic, focus, round_index)))
        for idx, speaker in enumerate(secondary):
            point = _speaker_specific_point(points, idx + len(secondary), round_index)
            role_hint = role_briefs[idx + 1] if idx + 1 < len(role_briefs) else _SECONDARY_ROLE_HINTS[(idx + round_index + 1) % len(_SECONDARY_ROLE_HINTS)]
            rebuilt.append((speaker, _secondary_followup_line(role_hint, point, round_index, idx, medical)))
        rebuilt.append((primary, _primary_response_line(_speaker_specific_point(points, round_index, round_index), round_index, medical)))
        for idx, speaker in enumerate(secondary):
            point = _speaker_specific_point(points, idx + len(secondary) * 2, round_index)
            role_hint = role_briefs[idx + 1] if idx + 1 < len(role_briefs) else _SECONDARY_ROLE_HINTS[(idx + 2) % len(_SECONDARY_ROLE_HINTS)]
            rebuilt.append((speaker, _secondary_commit_line(role_hint, point, round_index, idx, medical)))
        rebuilt.append((primary, _primary_plan_line(_speaker_specific_point(points, round_index + 1, round_index), topic, round_index, medical)))
        round_index += 1
        if round_index >= max_rounds:
            break

    if rebuilt and _content_length(rebuilt) > int(target_word_count * 1.03):
        trimmed: list[tuple[str, str]] = []
        for speaker, text in rebuilt:
            trimmed.append((speaker, text))
            if _content_length(trimmed) >= int(target_word_count * 0.995):
                break
        rebuilt = trimmed

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for speaker, text in rebuilt:
        normalized = _normalize_line_text(text)
        key = (speaker, normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append((speaker, normalized))
    return deduped


def repair_dialogue_quality(
    lines: list[tuple[str, str]],
    language: str,
    *,
    title: str = "",
    scenario: str = "",
    core_content: str = "",
    profile: dict[str, Any] | None = None,
    target_word_count: int = 1000,
    people_count: int | None = None,
    keywords: list[str] | None = None,
    generation_context: dict[str, Any] | None = None,
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    canonical = canonical_language(language)
    expected_people = max(1, int(people_count or len(_speaker_order(lines)) or 1))
    target = max(100, int(target_word_count or 1000))
    if canonical != "Chinese":
        return list(lines), {"language": canonical, "repaired": False, "reason": "non_chinese"}

    context = _normalize_generation_context(generation_context)
    force_rebuild = bool(context.get("discussion_axes") or context.get("role_briefs") or target >= 700)
    if not force_rebuild and not _needs_dialogue_repair(lines, expected_people, target):
        return list(lines), {"language": canonical, "repaired": False, "reason": "quality_ok"}

    repaired = _build_structured_chinese_dialogue(
        lines,
        title,
        scenario,
        core_content,
        profile,
        target,
        expected_people,
        [item for item in (keywords or []) if str(item or "").strip()],
        context,
    )
    return repaired, {
        "language": canonical,
        "repaired": True,
        "reason": "structured_rebuild" if force_rebuild else "quality_repair",
        "original_line_count": len(lines),
        "repaired_line_count": len(repaired),
        "target_word_count": target,
    }
