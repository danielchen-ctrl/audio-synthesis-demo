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

_DESCRIPTOR_PREFIX_RE = re.compile(
    r"^(核心对话内容|核心内容|补充要求|文本主题|主题模板|行业场景|场景类型|角色分工|讨论重点|重点讨论|目标输出|写作要求|参与角色|最终目标|主题|角色目标|推进阶段|风险检查点|成功标准|重点关注)\s*[:：]?\s*"
)
_INLINE_DESCRIPTOR_RE = re.compile(r"(核心对话内容|核心内容|文本主题|主题模板|行业场景|场景类型|角色分工|讨论重点|重点讨论|目标输出|写作要求|参与角色|最终目标|主题|角色目标|推进阶段|风险检查点|成功标准|重点关注)\s*[:：]\s*")
_GENERIC_FOCUS_TERMS = {
    "相关协作方",
    "相关协作方2",
    "相关协作方3",
    "当前情况",
    "当前现状",
    "关键背景",
    "下一步动作",
    "明确结论",
    "执行动作",
    "目标输出",
    "写作要求",
}

_ROLE_SPECIFIC_PACKS: list[tuple[tuple[str, ...], dict[str, list[str]]]] = [
    (
        ("服务端", "后端", "技术", "执行风险", "上线节奏", "回滚"),
        {
            "facts": ["接口返回码与幂等处理", "回调状态机与补单链路", "服务日志与异常兜底",
                      "灰度窗口与流量切换方案", "监控告警阈值设置"],
            "risks": ["回调状态回写不一致", "异步通知漏测", "异常单补偿缺口",
                      "灰度与回滚预案不完整", "上线窗口与业务高峰冲突"],
            "outputs": ["服务端测试范围", "接口校验点", "回滚与补偿方案",
                        "上线前置条件清单", "监控与告警配置"],
        },
    ),
    (
        ("客户端", "前端", "App", "用户体验", "体验", "反馈", "宣导"),
        {
            "facts": ["端侧唤起与结果页提示", "弱网重试与重复点击", "埋点回传与状态刷新",
                      "用户反馈渠道与响应机制", "关键路径可用性数据"],
            "risks": ["端侧提示与服务端状态不一致", "弱网场景体验失真", "埋点遗漏影响复盘",
                      "用户认知偏差导致误操作", "宣导节奏与上线时间错配"],
            "outputs": ["端侧验证清单", "交互验收口径", "端到端回归范围",
                        "用户反馈收集方案", "宣导材料准备清单"],
        },
    ),
    (
        ("产品", "业务负责人", "增长", "现状和问题", "现状"),
        {
            "facts": ["业务规则边界", "异常流程与用户提示", "上线验收口径",
                      "当前业务目标完成情况", "主要阻塞点与依赖项"],
            "risks": ["规则口径反复变更", "验收标准不统一", "异常路径没有业务兜底",
                      "业务目标与执行进度脱节", "跨部门依赖未提前对齐"],
            "outputs": ["需求冻结清单", "规则确认稿", "上线验收标准",
                        "业务进展汇报", "跨部门协同行动项"],
        },
    ),
    (
        ("数据", "分析", "指标", "验证"),
        {
            "facts": ["指标口径与样本范围", "监控看板与异常阈值", "复盘所需数据留痕",
                      "实验对照组设计与样本量", "数据回收完整性"],
            "risks": ["指标口径不统一", "监控阈值失真", "复盘数据缺口",
                      "实验样本量不足影响结论", "数据回收延迟导致决策滞后"],
            "outputs": ["数据口径说明", "监控指标清单", "效果复盘模板",
                        "实验结果报告", "数据质量验收标准"],
        },
    ),
    (
        ("运营", "会员运营", "活动运营", "时间", "资源约束", "排期", "协作", "分工", "外部依赖", "配合"),
        {
            "facts": ["活动触达节奏", "用户分层与触达路径", "资源位与内容准备度",
                      "时间节点与资源分配情况", "跨部门协作依赖清单"],
            "risks": ["触达节奏与资源位错配", "活动口径前后台不一致", "复盘数据断层",
                      "资源排期与优先级冲突", "外部依赖交付不及时"],
            "outputs": ["执行排期表", "运营口径说明", "触达与复购复盘表",
                        "资源分配方案", "跨部门协作确认清单"],
        },
    ),
    (
        ("门店",),
        {
            "facts": ["门店执行动作", "一线反馈与异常案例", "门店人员培训准备度"],
            "risks": ["门店执行标准不统一", "异常反馈回流不及时", "培训不到位影响落地"],
            "outputs": ["门店动作清单", "反馈收集表", "执行培训安排"],
        },
    ),
    (
        ("患者", "家属"),
        {
            "facts": ["症状变化记录", "用药执行情况", "复查时间安排"],
            "risks": ["症状变化被忽略", "用药执行不到位", "复查节奏被拖延"],
            "outputs": ["复查提醒单", "家庭观察重点", "异常反馈方式"],
        },
    ),
]

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
    updated = _INLINE_DESCRIPTOR_RE.sub("", updated)
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


def _strip_descriptor_prefix(text: str) -> str:
    updated = str(text or "").strip()
    while updated:
        next_value = _DESCRIPTOR_PREFIX_RE.sub("", updated).strip()
        if next_value == updated:
            break
        updated = next_value
    return updated


def _normalize_topic_candidate(text: str, limit: int = 20) -> str:
    updated = _strip_descriptor_prefix(text)
    if not updated:
        return ""
    updated = re.sub(r"^(围绕|关于)", "", updated)
    updated = re.sub(r"^(先对齐|比较|收敛|拆开|明确|形成|负责把|推动|补充|说明|判断)", "", updated)
    updated = re.sub(r"(进行真实自然的多轮.*|展开真实自然的多轮.*|多轮.*对话|场景对话|评审会对话|进行讨论|展开讨论)$", "", updated)
    updated = re.sub(r"(中的现状目标和关键背景|对应的取舍与优先级|的下一步方案责任分工和验证口径|有明确负责人验证方式和时间点)$", "", updated)
    updated = re.sub(r"(进行真实自然的多轮.*|展开真实自然的多轮.*|多轮.*对话|场景对话|评审会对话|进行讨论|展开讨论)$", "", updated)
    updated = re.sub(r"\s+", "", updated)
    updated = updated.strip("“”\"'《》[]【】")
    updated = updated.strip("，。；;：:、")
    if not updated:
        return ""
    if updated in _GENERIC_FOCUS_TERMS:
        return ""
    return updated[:limit] if len(updated) > limit else updated


def _split_meaningful_pieces(text: str) -> list[str]:
    updated = str(text or "").strip()
    if not updated:
        return []
    updated = _strip_descriptor_prefix(updated)
    updated = re.sub(r"对话中必须明确体现这些关键词[——:：-]*", "", updated)
    updated = re.sub(r"(请生成自然、真实、口语化的多轮对话文本|请生成真实自然的多轮对话文本)", "", updated)
    pieces: list[str] = []
    for piece in re.split(r"[\n,，。；;、/｜|]+", updated):
        piece = _strip_descriptor_prefix(piece.strip())
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


def _topic_ref(topic: str, index: int) -> str:
    """Return varied references to the topic to avoid mechanical repetition.

    index % 4 == 0  → full topic (e.g., "AI产品付费转化策略讨论")
    index % 4 == 1  → pronoun  "这件事" / "这块"
    index % 4 == 2  → first meaningful phrase extracted from topic
    index % 4 == 3  → "这个议题"
    """
    bucket = index % 4
    if bucket == 0:
        return topic
    if bucket == 1:
        return "这块" if len(topic) <= 8 else "这件事"
    if bucket == 2:
        pieces = _split_meaningful_pieces(topic)
        short = pieces[0] if pieces else topic
        return short if short and short != topic else "这个问题"
    return "这个议题"


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
        role_objectives = _context_role_objectives(generation_context, role_briefs, _split_focus_candidates(core_content, scenario, title), topic)
        for index, keyword in enumerate(missing_keywords):
            speaker = order[(index + 1) % len(order)] if len(order) > 1 else primary_speaker
            injected = False
            for pos in range(len(updated) - 1, -1, -1):
                line_speaker, line_text = updated[pos]
                if line_speaker != speaker or _keyword_in_text(line_text, keyword):
                    continue
                speaker_index = order.index(speaker) if speaker in order else 0
                role_hint = role_briefs[speaker_index] if speaker_index < len(role_briefs) else "相关角色"
                objective_hint = _objective_summary(role_objectives[speaker_index], keyword) if speaker_index < len(role_objectives) else keyword
                clause_variants = [
                    f"尤其是{keyword}这块得落到明确负责人和验证口径",
                    f"这里最容易被忽略的其实是{keyword}，后面不补清楚就会影响{objective_hint}",
                    f"另外{keyword}不能只停在提一下，最好直接说到怎么做、谁来跟进",
                    f"{keyword}这块如果不讲透，站在{role_hint}角度后面会一直担心执行跑偏",
                ]
                clause = (
                    clause_variants[index % len(clause_variants)]
                    if speaker == primary_speaker
                    else clause_variants[(index + speaker_index + 1) % len(clause_variants)]
                )
                updated[pos] = (line_speaker, _normalize_line_text(f"{line_text.rstrip('。！？!?；;，,')}，{clause}。"))
                injected = True
                break
            if injected:
                continue
            speaker_index = order.index(speaker) if speaker in order else 0
            joined_role = role_briefs[speaker_index] if speaker_index < len(role_briefs) else "相关角色"
            objective_hint = _objective_summary(role_objectives[speaker_index], keyword) if speaker_index < len(role_objectives) else keyword
            if speaker == primary_speaker:
                additions.append((speaker, f"另外，围绕{topic}这件事，{keyword}这块也得重点说清楚，不然后面很难把{objective_hint}收住。"))
            else:
                additions.append((speaker, f"从{joined_role}这边看，我现在最关心的就是{keyword}，因为这会直接影响{objective_hint}，想听听更具体的判断。"))
        return [*updated, *additions], missing_keywords

    speaker_label = primary_speaker
    appended_text = f"We should explicitly cover these keywords in the dialogue: {', '.join(missing_keywords)}."
    return [*lines, (speaker_label, appended_text)], missing_keywords


_EN_BUSINESS_NAMES = [
    "Alex Chen", "Sarah Johnson", "Michael Zhang", "Emma Liu", "Kevin Wang",
    "Lisa Park", "David Kim", "Jennifer Wu", "Robert Lee", "Amy Brown",
    "James Scott", "Rachel Tang", "Brian Xu", "Cynthia Ho", "Daniel Yu",
]

# ── Varied fallback lines for English CJK-replacement ────────────────────────
# Lead (primary speaker): assertive, agenda-driving
_EN_FALLBACK_LEAD: list[str] = [
    "Let me walk everyone through where we stand on this.",
    "I want to make sure we're aligned on the key priorities before we go further.",
    "Let's keep our focus on the deliverable and work backwards from there.",
    "There are a few angles here — let me break them down one by one.",
    "We should nail down the decision criteria before we finalize anything.",
    "Let me flag a couple of dependencies we need to resolve first.",
    "I'd like to get everyone's read on the risk exposure here.",
    "Before we move on, let me clarify the scope boundary.",
    "Let's make sure the next actions are specific and have owners.",
    "I want to double-check our assumptions before we commit to this direction.",
    "Let me surface the two main trade-offs and we can decide together.",
    "We need to be honest about the timeline pressure here.",
    "Let me make sure we capture this as a formal action item.",
    "I want to revisit the success criteria to make sure they're realistic.",
    "Let me pull in some context that might change how we frame this.",
    "We should separate the short-term fix from the longer-term solution.",
    "Let me be direct — there are resource constraints we need to work around.",
    "I'll summarize what I'm hearing and we can course-correct if needed.",
    "Let's stay focused on what we can actually decide in this meeting.",
    "Before we close this topic, I want to make sure nothing is left hanging.",
    "Let me take that offline and come back with a concrete recommendation.",
    "There's an important constraint I haven't mentioned yet — let me bring it up now.",
    "I want to make sure we document the rationale, not just the decision.",
    "Let me check if we have consensus on this before we proceed.",
    "I'd like to propose a clear decision framework here.",
    "Let me set the context for why this matters right now.",
    "We should define what a good outcome looks like before we debate the path.",
    "Let me be specific about what I need from the team on this.",
    "I want to validate our assumptions with real data before we finalize.",
    "Let's pressure-test this plan and identify the weak spots.",
]

# Support (non-primary speakers): responsive, collaborative
_EN_FALLBACK_SUPPORT: list[str] = [
    "That makes sense — I'll align my workstream with that direction.",
    "Agreed. Let me add what I'm seeing from our side.",
    "I can take that on — let me share my current read on it first.",
    "Good point. I'll need to loop in my team before we commit.",
    "That's consistent with what we've been tracking.",
    "I see the trade-off — let me weigh in on the implementation side.",
    "I'll follow up on that and get you a concrete answer by end of week.",
    "From our perspective, the main blocker is the dependency on the upstream team.",
    "That's a valid concern — here's how I'd approach it.",
    "I can support that direction, but I want to flag a potential complication.",
    "Makes sense to me. I'll own the coordination on our end.",
    "I'll confirm the details and report back at the next checkpoint.",
    "I want to make sure I understand the ask correctly before I commit.",
    "Let me think through the downstream impact of that decision.",
    "I'm on board with that. Let me check on timeline feasibility.",
    "I'll raise this with the relevant stakeholders and come back with a position.",
    "That's a fair point — I'll factor that into our planning.",
    "I can get you a clearer picture after I pull the latest data.",
    "I'll take note of that and make sure it's reflected in my deliverable.",
    "Happy to dive deeper on that — it's been a concern on our side too.",
    "I'll align with the team and confirm we're on the same page.",
    "That approach works for me. I'll coordinate accordingly.",
    "I want to add some context that might be relevant here.",
    "Let me push back gently on one point — I think there's a better framing.",
    "Understood. I'll factor that into the updated timeline.",
    "That's helpful framing. Let me think about what it means for our side.",
    "I'll make sure this gets communicated clearly downstream.",
    "Good call — I was going to raise the same concern.",
    "I can absorb that scope, but I'll need to adjust my other priorities.",
    "Let me confirm ownership on that action so nothing falls through the cracks.",
]

# ── Japanese & Korean contamination filter ───────────────────────────────────

def _is_chinese_contamination_ja(text: str) -> bool:
    """
    True if the line is Chinese contamination in a Japanese dialogue.

    Key insight: legitimate Japanese sentences almost always contain kana
    (hiragana/katakana) for grammar particles (は、が、を、の、で...) and
    verb endings (ます、です...). A line with substantial CJK content but
    ZERO kana is virtually always a Chinese-leaked line, even when mixed
    with English technical terms (which dilute the CJK ratio below naive
    percentage thresholds).

    Rule: no kana AND ≥4 CJK chars → Chinese contamination.
    The min-count guard (≥4) prevents false-positives on lines that contain
    only 1-3 CJK chars in otherwise English / non-CJK text.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    kana_count = sum(1 for c in chars if "\u3040" <= c <= "\u30ff")
    if kana_count:
        return False  # any kana → legitimate Japanese content
    cjk_count = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return cjk_count >= 4


def _is_chinese_contamination_ko(text: str) -> bool:
    """
    True if line has significant CJK but negligible Hangul — Chinese leakage in a KO dialogue.
    Korean does not use CJK characters, so any CJK presence with low Hangul is suspect.
    The min-count guard (≥4 CJK) avoids false-positives on lines with only 1-3 CJK chars.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    cjk_count    = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    hangul_count = sum(1 for c in chars if "\uac00" <= c <= "\ud7a3")
    if hangul_count:
        return False  # any Hangul → legitimate Korean content
    return cjk_count >= 4


def _is_chinese_contamination_latin(text: str) -> bool:
    """
    True if a Latin-script language line (FR/DE/ES/PT) contains ≥4 CJK characters.
    These languages use zero CJK; any CJK presence of 4+ chars is Chinese leakage.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    cjk_count = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return cjk_count >= 4


_LATIN_SCRIPT_LANGUAGES = frozenset({"French", "German", "Spanish", "Portuguese"})


def _filter_cjk_contamination(
    lines: list[tuple[str, str]],
    language: str,
) -> tuple[list[tuple[str, str]], int]:
    """
    Remove lines that are Chinese contamination for Japanese, Korean, or Latin-script dialogues.
    Returns (filtered_lines, removed_count).
    Japanese: keep lines that have kana (genuine JA); remove CJK-only lines.
    Korean:   keep lines that have Hangul (genuine KO); remove CJK-only lines.
    FR/DE/ES/PT: remove any line with ≥4 CJK chars (these use pure Latin script).
    """
    if language == "Japanese":
        check = _is_chinese_contamination_ja
    elif language == "Korean":
        check = _is_chinese_contamination_ko
    elif language in _LATIN_SCRIPT_LANGUAGES:
        check = _is_chinese_contamination_latin
    else:
        return lines, 0

    filtered: list[tuple[str, str]] = []
    removed = 0
    for speaker, text in lines:
        normalized = _normalize_line_text(text)
        if normalized and check(normalized):
            removed += 1
        else:
            filtered.append((speaker, normalized or text))
    return filtered, removed

_EN_TEMPLATE_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^Based on (?:our previous discussion|the discussion so far),?\s*I (?:suggest|recommend) we have a few (?:options|choices)[.:]?", re.I), "Let me lay out the key options on the table."),
    (re.compile(r"^Let me summarize what we[''']ve discussed[.:]?$", re.I), "Let me quickly recap the key points before we move on."),
    (re.compile(r"^I(?:'ll| will) need to look into this further and get back to you[.:]?$", re.I), "Let me follow up on this and come back with specifics."),
    (re.compile(r"^Option\s*1\s*[:：]", re.I), "One approach would be to start with the most critical piece and iterate from there."),
    (re.compile(r"^Option\s*2\s*[:：]", re.I), "Alternatively, we could prepare the full plan first before rolling out."),
    (re.compile(r"^(?:Okay|OK|Good),?\s*let(?:'s| us) (?:summarize|wrap up)[.:]?$", re.I), "Let me pull together the key takeaways."),
    (re.compile(r"^I (?:understand|see)\.\s*That(?:'s| is) (?:indeed )?something to note\.$", re.I), "Got it — let's make sure this gets properly tracked going forward."),
    (re.compile(r"^I (?:understand|see)\.\s*That(?:'s| is) indeed something to note\.$", re.I), "Noted — I'll make sure that's reflected in the plan."),
]


def _build_english_speaker_names(lines: list[tuple[str, str]]) -> dict[str, str]:
    order = _speaker_order(lines)
    rng = random.Random(random.SystemRandom().randrange(1, 2**32))
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for speaker in order:
        available = [n for n in _EN_BUSINESS_NAMES if n not in used] or _EN_BUSINESS_NAMES
        chosen = rng.choice(available)
        used.add(chosen)
        mapping[speaker] = chosen
    return mapping


def _context_topic_fragment_en(title: str, scenario: str, core_content: str) -> str:
    """Return a short English topic phrase for use in English dialogue rewrites."""
    for candidate in (title, scenario, core_content):
        text = str(candidate or "").strip()
        if not text or _contains_cjk(text):
            continue
        # Take first sentence or first ~40 chars
        first = re.split(r"[.!?\n]", text)[0].strip()
        first = re.sub(r"\s+", " ", first)
        if 6 <= len(first) <= 80:
            return first[:60]
    return "the agenda items"


def _rewrite_english_line(
    speaker: str,
    raw_text: str,
    primary_speaker: str,
    speaker_names: dict[str, str],
    topic: str,
) -> str:
    original = _normalize_line_text(raw_text)
    if not original:
        return ""

    # <<Core:...>> or "The most important thing is" → remove the marker line entirely
    # (caller skips empty returns)
    if _CORE_MARKER_RE.search(original) or re.search(r"the most important thing is", original, re.IGNORECASE):
        return ""

    # Risk Alert lines → remove
    if _RISK_ALERT_RE.search(original):
        return ""

    # Lines containing placeholder role names → replace with proper English intro
    if _PLACEHOLDER_ROLE_RE.search(original):
        if speaker == primary_speaker:
            return f"Good morning everyone. Let's get started and align on {topic} today."
        return f"Happy to be here. I'll be focused on key constraints and risk areas around {topic}."

    # Template rewrites for known verbose English boilerplate
    for pattern, replacement in _EN_TEMPLATE_REWRITES:
        if pattern.match(original):
            return replacement

    # Lines with heavy CJK content are Chinese leakage from a mixed-language prompt.
    # Return a sentinel tuple so the caller can pick a varied fallback from the pool.
    non_space = [c for c in original if not c.isspace()]
    if non_space:
        cjk_count = sum(1 for c in non_space if "\u4e00" <= c <= "\u9fff")
        if cjk_count / len(non_space) > 0.25:
            return "\x00CJK_FALLBACK\x00"  # sentinel — handled in caller

    return _normalize_line_text(original)


def _polish_english_generated_lines(
    lines: list[tuple[str, str]],
    scenario: str,
    core_content: str,
    profile: dict[str, Any] | None,
    *,
    title: str = "",
) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    if not lines:
        return [], {"language": "English", "rewrite_count": 0, "rewrites": []}

    topic = _context_topic_fragment_en(title, scenario, core_content)
    speaker_names = _build_english_speaker_names(lines)
    primary_speaker = _speaker_order(lines)[0]

    rewritten: list[tuple[str, str]] = []
    rewrite_meta: list[dict[str, str]] = []

    # Varied fallback pools — shuffle once per document, then drain in order
    rng = random.Random(random.SystemRandom().randrange(1, 2**32))
    lead_pool    = _EN_FALLBACK_LEAD[:]
    support_pool = _EN_FALLBACK_SUPPORT[:]
    rng.shuffle(lead_pool)
    rng.shuffle(support_pool)
    lead_idx    = 0
    support_idx = 0
    used_lines: set[str] = set()

    def _next_fallback(is_lead: bool) -> str:
        nonlocal lead_idx, support_idx
        pool = lead_pool if is_lead else support_pool
        idx  = lead_idx  if is_lead else support_idx
        # Cycle through pool avoiding already-used lines
        for offset in range(len(pool)):
            candidate = pool[(idx + offset) % len(pool)]
            if candidate not in used_lines:
                if is_lead:
                    lead_idx = (idx + offset + 1) % len(pool)
                else:
                    support_idx = (idx + offset + 1) % len(pool)
                used_lines.add(candidate)
                return candidate
        # All exhausted — just advance index
        fallback_text = pool[idx % len(pool)]
        if is_lead:
            lead_idx = (idx + 1) % len(pool)
        else:
            support_idx = (idx + 1) % len(pool)
        return fallback_text

    for speaker, raw_text in lines:
        original = _normalize_line_text(raw_text)
        updated = _rewrite_english_line(speaker, raw_text, primary_speaker, speaker_names, topic)
        if not updated:
            continue
        if updated == "\x00CJK_FALLBACK\x00":
            updated = _next_fallback(speaker == primary_speaker)
        if updated in used_lines and updated not in (
            # Allow opening lines to repeat if pool is tiny
            lead_pool[:2] + support_pool[:2]
        ):
            updated = _next_fallback(speaker == primary_speaker)
        used_lines.add(updated)
        rewritten.append((speaker, updated))
        if updated != original:
            rewrite_meta.append({"speaker": speaker, "before": original, "after": updated})

    if not rewritten:
        fallback = f"Let's get started and make sure we cover all the key points on {topic} today."
        rewritten = [(primary_speaker, fallback)]
        rewrite_meta.append({"speaker": primary_speaker, "before": "", "after": fallback})

    return rewritten, {
        "language": "English",
        # Always >= 1 so the caller replaces original lines with polished ones.
        "rewrite_count": max(1, len(rewrite_meta)),
        "rewrites": rewrite_meta,
        "speaker_names": speaker_names,
    }


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
        return _polish_english_generated_lines(lines, scenario, core_content, profile, title=title)

    rules = load_text_naturalness_rules().get("languages", {}).get(canonical, {})
    if not isinstance(rules, dict):
        rules = {}

    exact_replacements = rules.get("exact_replacements") or {}
    speaker_variants = rules.get("speaker_variants") or {}
    regex_replacements = rules.get("regex_replacements") or []

    # Step 1: Apply YAML exact/regex rules to replace known contamination patterns
    # with proper target-language equivalents.  We do this BEFORE the CJK filter so
    # that formerly-Chinese lines that were converted by the rules have kana/hangul
    # and are not immediately filtered away.
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

    # Step 2: CJK contamination filter on the YAML-processed lines.
    # After YAML rules, formerly-Chinese lines converted to JA/KO now contain kana/hangul
    # and will pass the filter.  Only lines that were NOT covered by YAML rules AND are
    # still Chinese are removed here.
    # Threshold: keep filtered result if ≥3 lines survive (no percentage floor — the
    # YAML replacements above already generated meaningful JA/KO content, so even a
    # short filtered result is usable).
    cjk_lines_removed = 0
    if canonical in ("Japanese", "Korean") or canonical in _LATIN_SCRIPT_LANGUAGES:
        filtered2, removed2 = _filter_cjk_contamination(rewritten, canonical)
        if removed2 and filtered2 and len(filtered2) >= 3:
            rewritten = filtered2
            cjk_lines_removed = removed2

    if not rules:
        # No YAML rules path — just return (possibly filtered) lines
        return list(rewritten), {
            "language": canonical,
            "rewrite_count": cjk_lines_removed,
            "rewrites": [],
            "cjk_lines_removed": cjk_lines_removed,
        }

    return rewritten, {
        "language": canonical,
        # Count CJK removals as rewrites so the caller replaces original lines with cleaned ones
        "rewrite_count": len(rewrite_meta) + cjk_lines_removed,
        "rewrites": rewrite_meta,
        "cjk_lines_removed": cjk_lines_removed,
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
    "关键链路",
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

_DOMAIN_REALISM_GUIDE = {
    "医疗健康": {
        "facts": ["这段时间的症状变化", "检查指标和复查结果", "用药执行情况", "家属配合度",
                  "随访时间窗口合理性", "患者依从性评估", "并发症风险排查", "生活方式干预执行"],
        "risks": ["复查节点拖延", "症状变化判断偏差", "用药依从性不足", "风险提示没有同步到位",
                  "依从性干预缺失", "随访间隔过长漏诊", "家属信息传递错位", "多科室协作断层"],
        "outputs": ["复查安排", "观察重点", "异常处理提醒", "家庭配合动作",
                    "用药调整方案", "随访提醒安排", "生活方式干预建议", "家属沟通要点"],
    },
    "人力资源与招聘": {
        "facts": ["岗位缺口和业务优先级", "候选人画像匹配度", "渠道转化效率", "到岗时间压力",
                  "HC审批进度", "内推激活情况", "面试通过率趋势", "同类岗位竞争薪酬"],
        "risks": ["画像不清导致投放失焦", "业务需求反复变化", "关键岗位补位过慢", "offer转化不稳定",
                  "HC冻结风险上升", "面试官配合度不足", "候选人放弃率偏高", "内推池质量下滑"],
        "outputs": ["招聘推进节奏", "渠道分配方案", "候选人筛选标准", "业务对齐口径",
                    "面试安排节奏", "薪酬竞争力方案", "内推激励机制", "JD优化建议"],
    },
    "娱乐/媒体": {
        "facts": ["内容资源和排期情况", "品牌合作匹配度", "流量投放节奏", "商务回报预期",
                  "本周业务目标完成率", "跨部门协作阻塞点梳理", "重点项目里程碑偏差", "预算执行与计划偏差"],
        "risks": ["资源投入回收不成正比", "传播节奏失控", "品牌调性不匹配", "执行落地反复返工",
                  "目标进展滞后未及时升级", "资源配置与业务优先级错位", "跨团队对齐存在断层", "关键决策被搁置不推进"],
        "outputs": ["商务推进策略", "内容合作口径", "投放节奏安排", "复盘指标",
                    "战略周会决策纪要", "跨部门协同行动清单", "下周优先级排期", "风险跟进责任确认表"],
    },
    "建筑与工程行业": {
        "facts": ["现场进度和交付节点", "甲方反馈", "成本与采购情况", "施工配合条件",
                  "分包商配合情况", "材料到场时间", "安全检查记录", "天气与施工窗口影响"],
        "risks": ["交付节奏失控", "现场问题反复出现", "成本偏差扩大", "验收节点卡住",
                  "分包商拖期连锁", "材料质量不达标", "安全事故隐患升级", "业主变更需求频繁"],
        "outputs": ["交付问题清单", "现场整改动作", "验收准备安排", "责任分工",
                    "分包协调动作", "材料验收标准", "安全整改清单", "变更管理流程"],
    },
    "汽车行业": {
        "facts": ["车型投放节奏", "渠道准备度", "库存与区域反馈", "卖点表达和市场认知"],
        "risks": ["渠道准备不到位", "区域反馈滞后", "库存压力失衡", "卖点传达不一致"],
        "outputs": ["投放节奏表", "区域协同安排", "渠道沟通口径", "销售跟进动作"],
    },
    "咨询/专业服务": {
        "facts": ["客户真实诉求", "方案切入点", "关系推进状态", "交付能力匹配",
                  "决策链和核心利益方", "竞对方案对比", "项目里程碑对齐", "行业参考案例"],
        "risks": ["方案太泛导致竞争力不足", "客户关系推进停滞", "交付承诺过度", "报价缺乏支撑",
                  "关键人离场风险", "多方利益冲突升级", "项目延期影响续签", "交付标准理解偏差"],
        "outputs": ["客户拓展策略", "提案主线", "推进节奏", "角色分工",
                    "利益方沟通策略", "方案差异化要点", "项目节点确认表", "成功案例引用口径"],
    },
    "法律服务": {
        "facts": ["证据材料准备度", "风险边界判断", "合规要求", "客户关注点",
                  "客户损失量化依据", "对方证据瑕疵点", "司法解释适用范围", "和解可行性评估"],
        "risks": ["表述越界", "证据链不完整", "整改建议难执行", "上线前合规把关不足",
                  "证据链被质疑", "时效性风险", "对方主动推进节奏加快", "和解条件被拉低"],
        "outputs": ["法律判断结论", "整改建议", "审核口径", "落地安排",
                    "证据补全清单", "谈判底线设定", "诉讼推进节点", "和解方案框架"],
    },
    "金融/投资": {
        "facts": ["风险偏好和收益目标", "资金安排", "资产组合现状", "调整窗口",
                  "市场波动区间", "行业集中度判断", "流动性管理状态", "客户持仓期限偏好"],
        "risks": ["收益预期过高", "风险暴露集中", "配置节奏失衡", "客户理解偏差",
                  "持仓集中度过高", "流动性错配风险", "市场突发事件冲击", "客户风险承受误判"],
        "outputs": ["配置建议", "风险提示", "组合调整动作", "沟通口径",
                    "仓位调整建议", "流动性缓冲安排", "情景压力测试结论", "持仓期限匹配方案"],
    },
    "零售行业": {
        "facts": ["会员分层现状", "活动触达效果", "门店配合度", "复购转化数据",
                  "新会员获取成本", "会员等级流失情况", "跨渠道购买行为", "节假日流量预测"],
        "risks": ["活动策略不分层", "门店执行不到位", "优惠投入回收偏弱", "效果验证口径不统一",
                  "促销依赖型消费习惯固化", "线上线下价格冲突", "会员权益感知下降", "节假日备货不足"],
        "outputs": ["复购方案", "活动策略", "门店配合动作", "效果验证标准",
                    "会员等级激励优化", "跨渠道联动方案", "节假日营销节奏", "消费频次提升路径"],
    },
    "保险行业": {
        "facts": ["销售表现", "录音质检结果", "客户反馈", "培训执行情况",
                  "合规风险分类统计", "高频问题话术记录", "培训参与度数据", "客诉响应时效"],
        "risks": ["话术触碰红线", "培训改进未闭环", "团队差异扩大", "问题重复发生",
                  "误导性表述批量扩散", "质检覆盖率不足", "培训和实际行为脱节", "客诉升级影响声誉"],
        "outputs": ["质检结论", "培训改进动作", "管理要求", "复盘标准",
                    "合规红线话术更新", "质检覆盖扩展方案", "培训有效性验证方法", "客诉处理标准流程"],
    },
    "房地产": {
        "facts": ["客源结构", "案场转化情况", "渠道效率", "价格反馈",
                  "竞品楼盘去化节奏", "按揭贷款利率变化", "案场到访量趋势", "成交客户特征分析"],
        "risks": ["渠道投入回报失衡", "案场转化下滑", "客群匹配偏差", "价格策略迟滞",
                  "竞品降价压力传导", "政策调控节点不确定", "案场人效下滑", "成交周期拉长"],
        "outputs": ["去化提效方案", "渠道动作", "案场配合安排", "短期目标",
                    "渠道费用结构优化", "按揭政策利用方案", "案场人效提升措施", "月度去化目标分解"],
    },
    "人工智能/科技": {
        "facts": ["漏斗转化数据", "试用和付费表现", "用户价值感知", "实验结果",
                  "付费门槛满意度调研结论", "免费功能使用深度数据", "竞品定价策略对比", "付费用户续订率趋势"],
        "risks": ["转化门槛设置不当", "价值感知不足", "数据回收不完整", "实验节奏失控",
                  "免费用户滥用关键功能", "A/B测试样本量不足", "付费与免费功能边界模糊", "实验结论被提前采纳"],
        "outputs": ["转化方案", "实验计划", "产品优化方向", "验证指标",
                    "付费门槛调整建议", "试用期策略迭代方案", "用户分层付费路径", "价值传递改进计划"],
    },
    "制造业": {
        "facts": ["瓶颈工序情况", "设备效率", "良率波动", "排产协同状态",
                  "原材料库存与供应商情况", "质量检验批次合格率", "工单完成率与交期达成", "班组人员出勤情况"],
        "risks": ["瓶颈工序拖慢节奏", "设备异常反复出现", "良率波动放大", "异常处置滞后",
                  "原材料短缺连锁停产", "质检不合格批次扩散", "交期承诺无法履行", "关键班组技能流失"],
        "outputs": ["提效动作", "排产调整建议", "设备改善安排", "质量跟踪口径",
                    "物料采购优先级安排", "质检标准与返工流程", "交期达成保障方案", "技能培训和备岗计划"],
    },
    "测试开发": {
        "facts": ["链路覆盖情况", "灰度与压测结果", "监控告警准备度", "回滚与兜底方案",
                  "接口契约与版本兼容性", "数据一致性与幂等验证", "依赖服务稳定性", "上线审批与发布窗口"],
        "risks": ["异常链路漏测", "回调和幂等处理不完整", "灰度窗口与回滚预案不清", "准入标准和告警阈值模糊",
                  "接口版本兼容遗漏", "依赖服务故障传导未兜底", "压测场景与线上差异", "发布后监控盲区扩大"],
        "outputs": ["测试范围清单", "准入结论", "风险清单", "上线前动作",
                    "接口契约确认表", "幂等与补偿机制方案", "灰度发布节点设定", "监控告警规则更新"],
    },
    "商业化": {
        "facts": ["艺人/IP商业定位", "品牌匹配度评估", "报价策略与市场参考", "执行风险识别",
                  "转化目标与KPI设定", "合同关键条款", "独家与非独家授权范围", "合作方资源投入承诺"],
        "risks": ["品牌调性冲突", "报价过高导致谈判破裂", "执行兑现能力不足", "转化目标虚高",
                  "独家条款约束过严", "合作方资源落空", "档期与竞品冲突", "舆情风险预判缺失"],
        "outputs": ["商业化推进策略", "合作判断结论", "报价方案与谈判底线", "执行安排与分工",
                    "KPI拆解与验收标准", "合同关键条款清单", "风险对冲预案", "短期与长期合作路径"],
    },
    "医疗行业": {
        "facts": ["这段时间的症状变化", "检查指标和复查结果", "用药执行情况", "家属配合度",
                  "随访时间窗口合理性", "患者依从性评估", "并发症风险排查", "生活方式干预执行"],
        "risks": ["复查节点拖延", "症状变化判断偏差", "用药依从性不足", "风险提示没有同步到位",
                  "依从性干预缺失", "随访间隔过长漏诊", "家属信息传递错位", "多科室协作断层"],
        "outputs": ["复查安排", "观察重点", "异常处理提醒", "家庭配合动作",
                    "用药调整方案", "随访提醒安排", "生活方式干预建议", "家属沟通要点"],
    },
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
    role_objectives = [
        str(item or "").strip()
        for item in generation_context.get("role_objectives", [])
        if str(item or "").strip()
    ]
    stage_prompts = [
        str(item or "").strip()
        for item in generation_context.get("stage_prompts", [])
        if str(item or "").strip()
    ]
    risk_checks = [
        str(item or "").strip()
        for item in generation_context.get("risk_checks", [])
        if str(item or "").strip()
    ]
    success_signals = [
        str(item or "").strip()
        for item in generation_context.get("success_signals", [])
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
        "role_objectives": role_objectives,
        "discussion_axes": discussion_axes,
        "stage_prompts": stage_prompts,
        "risk_checks": risk_checks,
        "success_signals": success_signals,
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


def _context_role_objectives(
    generation_context: dict[str, Any] | None,
    role_briefs: list[str],
    focus_points: list[str],
    topic: str,
) -> list[str]:
    context = _normalize_generation_context(generation_context)
    objectives = [item for item in context.get("role_objectives", []) if item]
    if objectives:
        while len(objectives) < len(role_briefs):
            role_hint = role_briefs[len(objectives)]
            focus = focus_points[len(objectives) % max(len(focus_points), 1)] if focus_points else topic
            objectives.append(f"{role_hint}：围绕{focus}补充现状、风险和动作要求。")
        return objectives[: len(role_briefs)]

    generated: list[str] = []
    for index, role_hint in enumerate(role_briefs):
        focus = focus_points[index % max(len(focus_points), 1)] if focus_points else topic
        follow = focus_points[(index + 2) % max(len(focus_points), 1)] if focus_points else topic
        if index == 0:
            generated.append(f"{role_hint}：负责推动围绕{focus}和{follow}的判断收敛，拿到清晰结论。")
        else:
            generated.append(f"{role_hint}：围绕{focus}补充事实、风险和执行条件，不重复别人观点。")
    return generated


def _context_stage_prompts(generation_context: dict[str, Any] | None, topic: str, focus_points: list[str]) -> list[str]:
    context = _normalize_generation_context(generation_context)
    prompts = [item for item in context.get("stage_prompts", []) if item]
    if prompts:
        return prompts
    first = focus_points[0] if focus_points else topic
    second = focus_points[1] if len(focus_points) > 1 else first
    third = focus_points[2] if len(focus_points) > 2 else second
    return [
        f"先对齐{topic}的现状、目标和关键背景",
        f"围绕{first}、{second}拆开主要风险和约束",
        f"比较可执行方案，明确{third}对应的取舍与优先级",
        "收敛责任分工、时间点和验收方式",
    ]


def _context_risk_checks(generation_context: dict[str, Any] | None, focus_points: list[str], topic: str) -> list[str]:
    context = _normalize_generation_context(generation_context)
    checks = [item for item in context.get("risk_checks", []) if item]
    if checks:
        return checks
    results = [f"{point}是否边界不清或容易执行落空" for point in focus_points[:4]]
    if not results:
        results = [f"{topic}是否存在边界不清或执行落空的风险"]
    return results


def _context_success_signals(generation_context: dict[str, Any] | None, focus_points: list[str], topic: str) -> list[str]:
    context = _normalize_generation_context(generation_context)
    signals = [item for item in context.get("success_signals", []) if item]
    if signals:
        return signals
    results = [f"{point}有明确负责人、验证方式和时间点" for point in focus_points[:3]]
    if not results:
        results = [f"{topic}形成明确结论、分工和验收口径"]
    return results


def _role_specific_pack(role_hint: str, medical: bool) -> dict[str, list[str]]:
    if medical:
        for markers, pack in _ROLE_SPECIFIC_PACKS:
            if any(marker in role_hint for marker in markers):
                return pack
        return {
            "facts": ["症状变化记录", "用药执行情况", "复查时间安排"],
            "risks": ["症状变化被忽略", "复查节奏拖延", "家庭配合不到位"],
            "outputs": ["复查安排单", "观察重点说明", "异常反馈方式"],
        }
    for markers, pack in _ROLE_SPECIFIC_PACKS:
        if any(marker in role_hint for marker in markers):
            return pack
    return {
        "facts": ["当前现状", "关键约束", "执行准备度"],
        "risks": ["边界不清", "执行落空", "协作断层"],
        "outputs": ["行动清单", "责任分工", "验收口径"],
    }


def _objective_summary(objective: str, fallback: str) -> str:
    pieces = _split_meaningful_pieces(_strip_role_prefix(objective))
    for piece in pieces:
        if len(piece) >= 2:
            return piece
    return fallback


def _strip_role_prefix(text: str) -> str:
    updated = str(text or "").strip()
    if "：" in updated:
        return updated.split("：", 1)[1].strip()
    return updated


def _dialogue_quality_metrics(
    lines: list[tuple[str, str]],
    people_count: int,
    target_word_count: int,
    keywords: list[str],
) -> dict[str, Any]:
    text_length = _content_length(lines)
    rendered = [_normalize_line_text(text) for _, text in lines if _normalize_line_text(text)]
    unique_ratio = len(set(rendered)) / max(1, len(rendered))
    counts = _speaker_turn_counts(lines)
    covered_speakers = sum(1 for turns in counts.values() if turns >= 3)
    speaker_coverage = covered_speakers / max(1, people_count)
    keyword_hit_ratio = 1.0
    if keywords:
        all_text = "\n".join(text for _, text in lines)
        hit_count = sum(1 for keyword in keywords if _keyword_in_text(all_text, keyword))
        keyword_hit_ratio = hit_count / max(1, len(keywords))
    length_fit = 1.0 - min(1.0, abs(text_length - target_word_count) / max(100, target_word_count))
    score = round(unique_ratio * 0.35 + speaker_coverage * 0.25 + keyword_hit_ratio * 0.2 + length_fit * 0.2, 3)
    return {
        "content_length": text_length,
        "unique_ratio": round(unique_ratio, 3),
        "speaker_coverage": round(speaker_coverage, 3),
        "keyword_hit_ratio": round(keyword_hit_ratio, 3),
        "length_fit": round(length_fit, 3),
        "score": score,
    }


def _domain_realism_pack(generation_context: dict[str, Any] | None, profile: dict[str, Any] | None, medical: bool) -> dict[str, list[str]]:
    context = _normalize_generation_context(generation_context)
    domain = str(context.get("domain") or "").strip()
    use_case = str((profile or {}).get("use_case") or "")
    if not domain and "｜" in use_case:
        domain = use_case.split("｜", 1)[0].strip()
    if medical and not domain:
        domain = "医疗健康"
    pack = _DOMAIN_REALISM_GUIDE.get(domain)
    if pack:
        return pack
    return {
        "facts": ["当前现状", "关键约束", "协作条件", "执行节奏"],
        "risks": ["边界不清", "执行落空", "责任模糊", "结果无法验证"],
        "outputs": ["结论", "行动项", "验收标准", "责任分工"],
    }


def _realism_pick(items: list[str], index: int, fallback: str) -> str:
    if not items:
        return fallback
    return items[index % len(items)]


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
        if counts.get(speaker, 0) < 3:
            return True

    rendered = [_normalize_line_text(text) for _, text in lines if _normalize_line_text(text)]
    if not rendered:
        return True

    unique_ratio = len(set(rendered)) / max(1, len(rendered))
    if unique_ratio < 0.82:
        return True

    generic_secondary = sum(1 for speaker, text in lines if speaker != order[0] and _secondary_line_is_generic(text))
    if generic_secondary >= max(2, len(order) - 1):
        return True

    if _content_length(lines) < int(target_word_count * 0.96):
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
    candidates = [
        *preferred,
        *context_axes,
        *_split_focus_candidates(focus, topic),
    ]
    if len(candidates) < 4:
        candidates.extend(_split_focus_candidates(core_content))
    if len(candidates) < 4 and not context_axes:
        candidates.extend(_split_focus_candidates(scenario))
    ignored = {str(context.get("domain") or "").strip(), "测试开发", "通用业务"}
    deliverable = context.get("deliverable")
    if deliverable and len(candidates) < 5:
        candidates.extend(_split_focus_candidates(str(deliverable)))
    risk_checks = context.get("risk_checks", [])
    if len(candidates) < 6:
        candidates.extend(_split_focus_candidates(*risk_checks))
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
            f"刚才说的{point}我都听清楚了，我整合一下，先把最影响推进的卡点说清楚，再决定怎么往下走。",
            f"围绕{point}，大家提到了几个不同层面的关切，核心是现状和目标之间的差距，我们先把这个差距的主要原因对齐。",
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
        topic_ref = _topic_ref(topic, round_index + 1)
        variants = [
            f"所以围绕{point}，我的建议是先把事实、责任人和验收标准定住，再安排后续推进节奏。",
            f"接下来我们就按{topic_ref}这条主线往下走，先收敛关键风险，再决定资源和上线窗口怎么排。",
            f"你们刚才提到的点我都记住了，后面会围绕{point}把动作、边界和兜底方案讲得更落地一些。",
            f"这一段先收口，{point}的主要矛盾我们已经摆出来了，下一步按优先级逐项推进，不要一次全铺开。",
            f"围绕{topic_ref}，我们先把{point}这一段落稳，确认清楚执行条件和验收标准，再往后延伸。",
            f"我来整合一下，{point}相关的事实、责任和节奏基本对齐了，后面就按这个框架继续推，有偏差再及时调。",
        ]
    return variants[round_index % len(variants)]


def _primary_realism_line(
    point: str,
    topic: str,
    realism_pack: dict[str, list[str]],
    round_index: int,
    medical: bool,
) -> str:
    fact_hint = _realism_pick(realism_pack.get("facts", []), round_index, point)
    fact_hint_secondary = _realism_pick(realism_pack.get("facts", []), round_index + 1, fact_hint)
    risk_hint = _realism_pick(realism_pack.get("risks", []), round_index, point)
    output_hint = _realism_pick(realism_pack.get("outputs", []), round_index, topic)
    if medical:
        variants = [
            f"再往前走一步，{point}不能只停在感觉层面，像{fact_hint}和{risk_hint}这些都要对应到后面的{output_hint}上。",
            f"如果现在就准备后续安排，我更希望先把{fact_hint}核实清楚，不然{risk_hint}这类问题后面还是会反复出现。",
            f"围绕{topic}，我们最后一定要落到{output_hint}，否则前面关于{point}的讨论就很难真正帮到后续处理。",
        ]
    else:
        topic_ref = _topic_ref(topic, round_index)
        variants = [
            f"再往前走一步，{point}不能只停在判断层面，像{fact_hint}、{fact_hint_secondary}和{risk_hint}这些都要对应到后面的{output_hint}上。",
            f"如果现在就准备推进，我更希望先把{fact_hint}和{fact_hint_secondary}核实清楚，不然{risk_hint}这类问题后面还是会反复返工。",
            f"围绕{topic_ref}，我们最后一定要落到{output_hint}，否则前面关于{point}的讨论很容易停在口头上。",
            f"我补充一点，{point}这块如果{risk_hint}没有提前设防，后面{output_hint}的推进就会一直被卡住，所以{fact_hint}要现在就确认清楚。",
            f"说到底，{topic_ref}能不能顺利推进，很大程度上看{fact_hint}和{fact_hint_secondary}有没有讲到位，这是后面{output_hint}的前提。",
            f"最后提醒一下，{risk_hint}这类问题在{topic_ref}推进过程中很容易被忽视，但它直接影响{output_hint}，必须提前纳入{point}的讨论范围。",
        ]
    return variants[round_index % len(variants)]


def _secondary_commit_line(
    role_hint: str,
    point: str,
    success_signal: str,
    realism_pack: dict[str, list[str]],
    round_index: int,
    speaker_variant: int,
    medical: bool,
) -> str:
    role_pack = _role_specific_pack(role_hint, medical)
    fact_pool = [*role_pack.get("facts", []), *realism_pack.get("facts", [])]
    output_pool = [*role_pack.get("outputs", []), *realism_pack.get("outputs", [])]
    fact_hint = _realism_pick(fact_pool, round_index + speaker_variant, point)
    output_hint = _realism_pick(output_pool, round_index + speaker_variant + 1, success_signal)
    success_hint = _objective_summary(success_signal, point)
    if medical:
        variants = [
            f"明白了，那我会先把和{point}有关的{fact_hint}整理出来，再按{success_hint}去配合后面的{output_hint}。",
            f"好，那围绕{point}我这边会先把观察重点和异常反馈方式对齐，尤其把{fact_hint}补全，不拖到下次再说。",
            f"这样我就更清楚了，后面关于{point}我会按你说的节奏把{output_hint}和{success_hint}一起配合起来。",
        ]
    else:
        variants = [
            f"明白了，那我这边会先把和{point}有关的{fact_hint}、现状数据和阻塞项整理出来，再把{output_hint}对给大家。",
            f"好，那围绕{point}我会从{role_hint}这个角度先把责任人、时间点、验证方式和{success_hint}补齐，避免后面再来回改。",
            f"这样我就更清楚了，后面关于{point}我会先把{fact_hint}和{output_hint}准备扎实，再推进下一步。",
            f"明白，围绕{point}我先核实{fact_hint}，把阻塞项和边界条件理清楚，再跟大家同步{output_hint}的推进计划。",
            f"好的，那我从{role_hint}这边先把{point}对应的关键节点和验证口径整理一遍，{success_hint}这块在下次同步前确认到位。",
            f"我先跟进{fact_hint}和{output_hint}，有问题及时拉上{role_hint}一起处理，不等到最后才说堵住了。",
        ]
    return variants[(round_index + speaker_variant) % len(variants)]


def _primary_stage_open_line(
    stage_prompt: str,
    topic: str,
    point: str,
    deliverable: str,
    scene_goal: str,
    round_index: int,
    medical: bool,
) -> str:
    deliverable_hint = _objective_summary(deliverable, "明确结论")
    scene_hint = _objective_summary(scene_goal, topic)
    if scene_hint and (scene_hint in point or point in scene_hint):
        scene_hint = deliverable_hint
    if medical:
        variants = [
            f"我们先按“{stage_prompt}”往下聊，重点还是把{point}和{scene_hint}这两件事先讲明白。",
            f"这一轮我想先围绕{point}展开，不只是给结论，也要把为什么这么判断和后面怎么安排说清楚。",
            f"先别着急往后跳，我们先把{stage_prompt}这一段过扎实，最后才能把{deliverable_hint}落稳。",
            f"围绕{topic}，这一段先聚焦{point}，把现状、风险和后续安排都放到桌面上。",
        ]
    else:
        variants = [
            f"这一轮我们先按「{stage_prompt}」往下推，先把{point}和{scene_hint}这两件事讲透。",
            f"我想先围绕{point}展开，不只是判断对错，还要把会影响推进的关键约束一起摆出来。",
            f"先别急着往结论跳，先把{stage_prompt}这一段聊扎实，最后才能把{deliverable_hint}落到实处。",
            f"围绕{topic}，这一段先聚焦{point}，把事实、风险和动作一次对齐。",
            f"下面这一段聚焦{point}，{scene_hint}这部分最容易出现判断分歧，现在对齐比后面补救要省力。",
            f"{point}这块我多说几句，这里的取舍和优先级如果现在不讲清楚，{deliverable_hint}就很难落地。",
        ]
    return variants[round_index % len(variants)]


def _secondary_stage_line(
    role_hint: str,
    objective: str,
    point: str,
    risk_check: str,
    success_signal: str,
    realism_pack: dict[str, list[str]],
    stage_prompt: str,
    round_index: int,
    speaker_variant: int,
    medical: bool,
) -> str:
    objective_hint = _objective_summary(objective, point)
    risk_hint = _objective_summary(risk_check, point)
    success_hint = _objective_summary(success_signal, point)
    role_pack = _role_specific_pack(role_hint, medical)
    fact_pool = [*role_pack.get("facts", []), *realism_pack.get("facts", [])]
    risk_pool = [*role_pack.get("risks", []), *realism_pack.get("risks", [])]
    output_pool = [*role_pack.get("outputs", []), *realism_pack.get("outputs", [])]
    fact_hint = _realism_pick(fact_pool, round_index + speaker_variant, point)
    fact_hint_secondary = _realism_pick(fact_pool, round_index + speaker_variant + 1, fact_hint)
    risk_detail = _realism_pick(risk_pool, round_index + speaker_variant, risk_hint)
    output_hint = _realism_pick(output_pool, round_index + speaker_variant + 1, success_hint)
    if medical:
        variants = [
            f"从{role_hint}这边看，这一轮我最想先确认的是{point}，尤其{fact_hint}和{risk_detail}这两块要先说清楚，不然后面很难按{stage_prompt}继续往下走。",
            f"我补充一个实际情况，围绕{point}如果现在只停在笼统判断上，后面关于{output_hint}和{success_hint}就很容易落空，所以最好先把{fact_hint_secondary}讲细。",
            f"如果按{objective_hint}这个思路推进，那{point}至少要落到什么时候观察、什么时候复查、什么情况下要及时反馈，同时把{fact_hint}同步到位。",
            f"我再把顾虑说具体一点，{point}不只是一个判断题，它会直接牵动{risk_hint}和{output_hint}，所以这轮最好把边界和动作一次讲透。",
        ]
    else:
        variants = [
            f"从{role_hint}这边看，这一轮我最想先确认的是{point}，因为这会直接影响后面的排期和推进，尤其{fact_hint}、{fact_hint_secondary}以及{risk_detail}这几块不能糊过去。",
            f"我补充一个执行层面的判断，围绕{point}如果现在不把{fact_hint}和{output_hint}说到位，后面就算大家表面同意了，真正落到{success_hint}时也会反复返工。",
            f"如果按{objective_hint}这个思路往下走，那{point}最好先拆到可执行，比如谁负责、什么时候验证、出了问题怎么兜底，同时把{fact_hint_secondary}讲清楚。",
            f"站在{role_hint}角度，我希望这轮别只讲原则，最好直接把{point}对应的{fact_hint}、{risk_hint}和{output_hint}说到能执行，不然{stage_prompt}这一段就会悬着。",
            f"我先把{point}这块说具体一点，{fact_hint}必须先对齐，不然后续{output_hint}很容易只停在口头上，{risk_hint}的问题也容易被掩盖。",
            f"围绕{point}，我有个执行层面的关切：{risk_detail}如果{stage_prompt}这一段不提前设防，等问题暴露再补救代价会更大，所以我想先把{fact_hint_secondary}说透。",
            f"从{role_hint}这边看，{point}现在的主要卡点是{risk_hint}，要真正推进就得先把{output_hint}的边界和条件一次性说清楚，不能留到后面再扯。",
            f"我补充一个数据层面的判断，{point}如果{fact_hint}和{fact_hint_secondary}的口径没有先对齐，后续{success_hint}就很难量化验证，大家各说各的只会更乱。",
        ]
    return variants[(round_index + speaker_variant) % len(variants)]


def _primary_stage_close_line(
    stage_prompt: str,
    point: str,
    deliverable: str,
    success_signal: str,
    round_index: int,
    medical: bool,
) -> str:
    deliverable_hint = _objective_summary(deliverable, point)
    success_hint = _objective_summary(success_signal, point)
    if medical:
        variants = [
            f"好，这一段先收一下，围绕{point}至少已经把关键情况讲开了，后面我们就继续往{deliverable_hint}上收口。",
            f"你们刚才补得比较完整，下一步就按{stage_prompt}继续走，把{success_hint}也一并说到能执行。",
            f"这轮先到这里，围绕{point}我已经听到比较清楚的关切了，下面我们继续把{deliverable_hint}细化下来。",
            f"我先做个小结，{point}这块不能再停在感受层面了，后面要直接落到{success_hint}和具体安排。",
        ]
    else:
        variants = [
            f"好，这一段先收一下，围绕{point}至少已经把关键事实和约束讲开了，后面我们继续往{deliverable_hint}上收口。",
            f"你们刚才补得比较完整，下一步就按{stage_prompt}继续走，把{success_hint}也一并讲到能执行。",
            f"这轮先到这里，围绕{point}我已经听到比较清楚的分歧和风险了，下面我们继续把{deliverable_hint}细化下来。",
            f"我先做个小结，{point}这块不能再停在判断层面了，后面要直接落到{success_hint}和具体动作。",
            f"围绕{point}，这一段我们至少已经把主要矛盾摆出来了，后面就按{deliverable_hint}方向继续往下走，别再停在原地绕。",
            f"先收一下，{point}这块的事实和风险基本清楚了，接下来核心任务就是把{success_hint}落到有人负责、有时间节点的具体动作上。",
        ]
    return variants[round_index % len(variants)]


def _trim_dialogue_to_target(
    lines: list[tuple[str, str]],
    speakers: list[str],
    target_word_count: int,
    minimum_floor: int | None = None,
) -> list[tuple[str, str]]:
    target_ceiling = max(260, int(target_word_count * 1.01))
    minimum_floor = max(220, int(minimum_floor or 0))
    trimmed = list(lines)
    minimum_turns = {speaker: 3 for speaker in speakers}
    counts = _speaker_turn_counts(trimmed)
    while _content_length(trimmed) > target_ceiling and len(trimmed) > len(speakers) * 3:
        speaker, _ = trimmed[-1]
        projected_length = _content_length(trimmed[:-1])
        if counts.get(speaker, 0) > minimum_turns.get(speaker, 2) and (
            not minimum_floor or projected_length >= minimum_floor
        ):
            counts[speaker] -= 1
            trimmed.pop()
            continue
        removable_index = None
        for index in range(len(trimmed) - 1, -1, -1):
            candidate_speaker, _ = trimmed[index]
            candidate_trimmed = trimmed[:index] + trimmed[index + 1 :]
            if counts.get(candidate_speaker, 0) > minimum_turns.get(candidate_speaker, 2) and (
                not minimum_floor or _content_length(candidate_trimmed) >= minimum_floor
            ):
                removable_index = index
                break
        if removable_index is None:
            break
        candidate_speaker, _ = trimmed.pop(removable_index)
        counts[candidate_speaker] -= 1
    while _content_length(trimmed) > target_ceiling:
        shortened_index = None
        shortened_text = ""
        best_delta = 0
        for index, (speaker, text) in enumerate(trimmed):
            candidate = re.sub(r"[，,][^，,。！？!?]{10,40}[。！？!?]?$", "。", text)
            candidate = _normalize_line_text(candidate)
            if candidate == text or len(candidate) < 16:
                continue
            delta = len(re.sub(r"\s+", "", text)) - len(re.sub(r"\s+", "", candidate))
            if delta <= 0:
                continue
            candidate_trimmed = list(trimmed)
            candidate_trimmed[index] = (speaker, candidate)
            if minimum_floor and _content_length(candidate_trimmed) < minimum_floor:
                continue
            if delta > best_delta:
                shortened_index = index
                shortened_text = candidate
                best_delta = delta
        if shortened_index is None:
            break
        speaker, _ = trimmed[shortened_index]
        trimmed[shortened_index] = (speaker, shortened_text)
    return trimmed


def _stabilize_chinese_dialogue(
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
    current_order = _speaker_order(lines)
    speaker_map = {speaker: order[min(index, len(order) - 1)] for index, speaker in enumerate(current_order)}
    normalized: list[tuple[str, str]] = []
    for speaker, text in lines:
        mapped = speaker_map.get(speaker)
        cleaned = _normalize_line_text(text)
        if mapped and cleaned:
            normalized.append((mapped, cleaned))

    topic = _context_topic_fragment(title, scenario, core_content, profile)
    medical = _is_medical_context(scenario, core_content, profile)
    context = _normalize_generation_context(generation_context)
    role_briefs = _context_role_briefs(context, profile, len(order), medical)
    points = _structured_focus_points(topic, _core_focus_fragment(title, core_content, scenario, profile) or topic, keywords, core_content, scenario, medical, context)
    role_objectives = _context_role_objectives(context, role_briefs, points, topic)
    stage_prompts = _context_stage_prompts(context, topic, points)
    risk_checks = _context_risk_checks(context, points, topic)
    success_signals = _context_success_signals(context, points, topic)
    realism_pack = _domain_realism_pack(context, profile, medical)
    speaker_names = _build_chinese_speaker_names([(speaker, "") for speaker in order], scenario, core_content, profile)
    deliverable = context.get("deliverable") or f"围绕{topic}形成明确结论和下一步动作"
    scene_goal = context.get("scene_goal") or topic

    stabilized = list(normalized)
    counts = _speaker_turn_counts(stabilized)
    for speaker_index, speaker in enumerate(order):
        role_hint = role_briefs[speaker_index] if speaker_index < len(role_briefs) else f"相关协作方{speaker_index}"
        while counts.get(speaker, 0) < 3:
            turn_index = counts.get(speaker, 0)
            point = _speaker_specific_point(points, speaker_index + turn_index, turn_index)
            objective = role_objectives[speaker_index] if speaker_index < len(role_objectives) else f"{role_hint}：围绕{point}补充事实和动作要求。"
            risk_check = risk_checks[(speaker_index + turn_index) % len(risk_checks)] if risk_checks else point
            success_signal = success_signals[(speaker_index + turn_index) % len(success_signals)] if success_signals else deliverable
            stage_prompt = stage_prompts[(speaker_index + turn_index) % len(stage_prompts)]
            if turn_index == 0:
                if speaker_index == 0:
                    candidate = _build_intro_line(speaker, order[0], speaker_names, topic, medical, role_hint, scene_goal)
                else:
                    candidate = _secondary_intro_line(speaker_names.get(speaker, "李明"), role_hint, point, medical)
            elif turn_index == 1:
                if speaker_index == 0:
                    candidate = _primary_stage_open_line(stage_prompt, topic, point, deliverable, scene_goal, turn_index, medical)
                else:
                    candidate = _secondary_stage_line(
                        role_hint,
                        objective,
                        point,
                        risk_check,
                        success_signal,
                        realism_pack,
                        stage_prompt,
                        turn_index,
                        speaker_index,
                        medical,
                    )
            else:
                if speaker_index == 0:
                    candidate = _primary_stage_close_line(stage_prompt, point, deliverable, success_signal, turn_index, medical)
                else:
                    candidate = _secondary_commit_line(role_hint, point, success_signal, realism_pack, turn_index, speaker_index, medical)
            stabilized.append((speaker, candidate))
            counts[speaker] = counts.get(speaker, 0) + 1

    target_floor = max(260, int(target_word_count * 0.99))
    grow_round = 0
    while _content_length(stabilized) < target_floor:
        added_any = False
        for speaker_index, speaker in enumerate(order):
            role_hint = role_briefs[speaker_index] if speaker_index < len(role_briefs) else f"相关协作方{speaker_index}"
            point = _speaker_specific_point(points, speaker_index + grow_round, grow_round)
            objective = role_objectives[speaker_index] if speaker_index < len(role_objectives) else f"{role_hint}：围绕{point}补充事实和动作要求。"
            risk_check = risk_checks[(speaker_index + grow_round) % len(risk_checks)] if risk_checks else point
            success_signal = success_signals[(speaker_index + grow_round) % len(success_signals)] if success_signals else deliverable
            stage_prompt = stage_prompts[(speaker_index + grow_round) % len(stage_prompts)]
            if speaker_index == 0:
                candidate = _primary_plan_line(point, topic, grow_round, medical)
            elif grow_round % 2 == 0:
                candidate = _secondary_followup_line(role_hint, point, grow_round, speaker_index, medical)
            else:
                candidate = _secondary_stage_line(
                    role_hint,
                    objective,
                    point,
                    risk_check,
                    success_signal,
                    realism_pack,
                    stage_prompt,
                    grow_round,
                    speaker_index,
                    medical,
                )
            entry = (speaker, _normalize_line_text(candidate))
            if entry not in stabilized:
                stabilized.append(entry)
                added_any = True
            if _content_length(stabilized) >= target_floor:
                break
        if not added_any:
            break
        grow_round += 1
        if grow_round > 8:
            break

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for speaker, text in stabilized:
        key = (speaker, _normalize_line_text(text))
        if key[1] and key not in seen:
            seen.add(key)
            deduped.append(key)
    return _trim_dialogue_to_target(deduped, order, target_word_count, minimum_floor=target_floor)


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
    role_objectives = _context_role_objectives(context, role_briefs, points, topic)
    stage_prompts = _context_stage_prompts(context, topic, points)
    risk_checks = _context_risk_checks(context, points, topic)
    success_signals = _context_success_signals(context, points, topic)
    realism_pack = _domain_realism_pack(context, profile, medical)
    focus = "、".join(points[:2]) if len(points) > 1 else (points[0] if points else topic)
    deliverable = context.get("deliverable") or f"围绕{topic}形成明确结论和下一步动作"
    scene_goal = context.get("scene_goal") or topic

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
    target_floor = max(260, int(target_word_count * 1.01))
    max_rounds = max(10, min(18, int(target_word_count / 90)))
    while _content_length(rebuilt) < target_floor:
        stage_prompt = stage_prompts[round_index % len(stage_prompts)]
        stage_point = _speaker_specific_point(points, round_index, round_index)
        rebuilt.append((primary, _primary_stage_open_line(stage_prompt, topic, stage_point, deliverable, scene_goal, round_index, medical)))
        for idx, speaker in enumerate(secondary):
            role_hint = role_briefs[idx + 1] if idx + 1 < len(role_briefs) else _SECONDARY_ROLE_HINTS[idx % len(_SECONDARY_ROLE_HINTS)]
            point = _speaker_specific_point(points, idx + round_index, round_index)
            risk_check = risk_checks[(idx + round_index) % len(risk_checks)] if risk_checks else point
            success_signal = success_signals[(idx + round_index) % len(success_signals)] if success_signals else deliverable
            objective = role_objectives[idx + 1] if idx + 1 < len(role_objectives) else f"{role_hint}：围绕{point}补充事实和动作要求。"
            rebuilt.append(
                (
                    speaker,
                    _secondary_stage_line(
                        role_hint,
                        objective,
                        point,
                        risk_check,
                        success_signal,
                        realism_pack,
                        stage_prompt,
                        round_index,
                        idx,
                        medical,
                    ),
                )
            )
        rebuilt.append((primary, _primary_response_line(stage_point, round_index, medical)))
        for idx, speaker in enumerate(secondary):
            point = _speaker_specific_point(points, idx + len(secondary) + round_index, round_index)
            role_hint = role_briefs[idx + 1] if idx + 1 < len(role_briefs) else _SECONDARY_ROLE_HINTS[(idx + round_index + 1) % len(_SECONDARY_ROLE_HINTS)]
            success_signal = success_signals[(idx + round_index + 1) % len(success_signals)] if success_signals else deliverable
            rebuilt.append((speaker, _secondary_commit_line(role_hint, point, success_signal, realism_pack, round_index, idx, medical)))
        success_signal = success_signals[round_index % len(success_signals)] if success_signals else deliverable
        rebuilt.append((primary, _primary_stage_close_line(stage_prompt, stage_point, deliverable, success_signal, round_index, medical)))
        rebuilt.append((primary, _primary_realism_line(stage_point, topic, realism_pack, round_index, medical)))
        rebuilt.append((primary, _primary_plan_line(_speaker_specific_point(points, round_index + 1, round_index), topic, round_index, medical)))
        round_index += 1
        if round_index >= max_rounds:
            break

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for speaker, text in rebuilt:
        normalized = _normalize_line_text(text)
        key = (speaker, normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append((speaker, normalized))
    minimum_floor = max(260, int(target_word_count * 0.98))
    deduped = _trim_dialogue_to_target(deduped, order, target_word_count, minimum_floor=minimum_floor)
    if _content_length(deduped) < minimum_floor:
        extension_round = round_index + 1
        stage_prompt = stage_prompts[extension_round % len(stage_prompts)]
        for idx, speaker in enumerate(secondary):
            role_hint = role_briefs[idx + 1] if idx + 1 < len(role_briefs) else _SECONDARY_ROLE_HINTS[idx % len(_SECONDARY_ROLE_HINTS)]
            point = _speaker_specific_point(points, idx + extension_round, extension_round)
            objective = role_objectives[idx + 1] if idx + 1 < len(role_objectives) else f"{role_hint}：围绕{point}补充事实和动作要求。"
            risk_check = risk_checks[(idx + extension_round) % len(risk_checks)] if risk_checks else point
            success_signal = success_signals[(idx + extension_round) % len(success_signals)] if success_signals else deliverable
            candidate = _secondary_stage_line(
                role_hint,
                objective,
                point,
                risk_check,
                success_signal,
                realism_pack,
                stage_prompt,
                extension_round,
                idx + 1,
                medical,
            )
            if (speaker, candidate) not in seen:
                deduped.append((speaker, candidate))
                seen.add((speaker, candidate))
        closing = _primary_stage_close_line(stage_prompt, _speaker_specific_point(points, extension_round, extension_round), deliverable, success_signals[extension_round % len(success_signals)] if success_signals else deliverable, extension_round, medical)
        if (primary, closing) not in seen:
            deduped.append((primary, closing))
    return _trim_dialogue_to_target(deduped, order, target_word_count, minimum_floor=minimum_floor)


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

    # Universal cleanup for all languages: strip <<Core:...>> / <<核心:...>> / Risk Alert lines
    # that the LLM occasionally echoes back from the prompt template.
    _universal_cleaned = [
        (spk, txt) for spk, txt in lines
        if not _CORE_MARKER_RE.search(txt) and not _RISK_ALERT_RE.search(txt)
    ]
    _universal_changed = bool(_universal_cleaned) and len(_universal_cleaned) != len(lines)
    if _universal_cleaned:
        lines = _universal_cleaned

    if canonical != "Chinese":
        return list(lines), {
            "language": canonical,
            "repaired": _universal_changed,
            "reason": "marker_cleanup" if _universal_changed else "non_chinese",
        }

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
    quality_metrics = _dialogue_quality_metrics(
        repaired,
        expected_people,
        target,
        [item for item in (keywords or []) if str(item or "").strip()],
    )
    return repaired, {
        "language": canonical,
        "repaired": True,
        "reason": "structured_rebuild" if force_rebuild else "quality_repair",
        "original_line_count": len(lines),
        "repaired_line_count": len(repaired),
        "target_word_count": target,
        "quality_metrics": quality_metrics,
    }


def stabilize_dialogue_constraints(
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
        return list(lines), {"language": canonical, "stabilized": False, "reason": "non_chinese"}

    stabilized = _stabilize_chinese_dialogue(
        list(lines),
        title,
        scenario,
        core_content,
        profile,
        target,
        expected_people,
        [item for item in (keywords or []) if str(item or "").strip()],
        generation_context,
    )
    metrics = _dialogue_quality_metrics(
        stabilized,
        expected_people,
        target,
        [item for item in (keywords or []) if str(item or "").strip()],
    )
    return stabilized, {
        "language": canonical,
        "stabilized": True,
        "reason": "constraint_stabilized",
        "target_word_count": target,
        "quality_metrics": metrics,
    }
