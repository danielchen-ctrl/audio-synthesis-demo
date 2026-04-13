#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multilingual training data generation — FR / DE / ES / PT / YUE
=================================================================
Generates wc5000 training files for the 5 languages that currently have
no training data.

Generation strategy:
  - FR / DE / ES / PT: Generate in Chinese (which the LLM does well),
    then translate via Google Translate. This sidesteps the LLM's weak
    native generation for these languages.
  - YUE (Cantonese): Generate natively with language="Cantonese".
    Cantonese uses CJK script so CJK ratio check is skipped.

Generation matrix:
  14 templates × 5 languages × 5 speaker counts = 350 files

Usage:
  cd D:/ui_auto_test/demo_app
  python tools/generation/batch_multilang_training.py
"""

import re
import requests
import time
from pathlib import Path
from datetime import datetime
from collections import Counter

# ─── Config ────────────────────────────────────────────────────────────────
BASE_URL       = "http://127.0.0.1:8899"
OUT_DIR        = Path(__file__).resolve().parent.parent.parent / "demo" / "training_long_dialogue"
WC_TARGET      = 5000
RETRY_TIMES    = 3
RETRY_SLEEP    = 8
INTER_SLEEP    = 2
MAX_CJK_RATIO  = 0.05   # for Latin-script languages
MAX_REPEAT     = 4
MIN_CHARS      = 2000   # reject suspiciously short generations

# Google Translate
_GT_URL   = "https://translate.googleapis.com/translate_a/single"
_GT_CHUNK = 800
_NO_PROXY = {"http": None, "https": None}

SPEAKER_COUNTS = [2, 3, 4, 5, 6]

# Languages: use_translate=True → generate Chinese then translate
LANGUAGES = [
    {"short": "fr",  "backend": "French",     "display": "法语",      "gt_code": "fr",  "use_translate": True},
    {"short": "de",  "backend": "German",     "display": "德语",      "gt_code": "de",  "use_translate": True},
    {"short": "es",  "backend": "Spanish",    "display": "西班牙语",  "gt_code": "es",  "use_translate": True},
    {"short": "pt",  "backend": "Portuguese", "display": "葡萄牙语",  "gt_code": "pt",  "use_translate": True},
    {"short": "yue", "backend": "Cantonese",  "display": "粤语",      "gt_code": None,  "use_translate": False},
]

TEMPLATES = [
    {
        "id": "ai_tech",
        "industry": "人工智能/科技",
        "label": "人工智能/科技｜付费转化",
        "scenario": "AI产品付费转化策略讨论",
        "core_content": (
            "围绕付费转化漏斗优化、付费门槛设计与试用策略展开深度讨论，"
            "分析数据回收方式和用户价值感知提升方案，形成付费转化优化方案和实验计划"
        ),
        "scenario_en": "AI Product Paid Conversion Strategy Discussion",
        "core_content_en": (
            "In-depth discussion on optimizing paid conversion funnels, payment threshold design and free-trial strategies, "
            "analyzing data collection methods and user value perception improvements, "
            "forming a paid conversion optimization plan and experiment roadmap."
        ),
    },
    {
        "id": "media_strategy",
        "industry": "娱乐/媒体",
        "label": "娱乐/媒体｜战略周会",
        "scenario": "娱乐媒体公司战略周会讨论",
        "core_content": (
            "围绕业务目标进展、资源投入分配、重点风险识别和下周行动计划展开讨论，"
            "形成战略周会的重点决策和分工安排"
        ),
        "scenario_en": "Entertainment Media Company Strategic Weekly Meeting",
        "core_content_en": (
            "Discussion on business objective progress, resource allocation decisions, key risk identification, "
            "and next-week action plans, forming key decisions and clear task assignments for the strategic weekly meeting."
        ),
    },
    {
        "id": "test_dev",
        "industry": "测试开发",
        "label": "测试开发｜支付项目",
        "scenario": "支付项目测试质量复盘",
        "core_content": (
            "围绕支付项目的链路完整性、异常兜底策略和上线风险展开讨论，"
            "涵盖支付接入、下单回调、退款安全、对账差错和稳定性准入，"
            "形成测试范围、风险清单和上线准入结论"
        ),
        "scenario_en": "Payment Project Test Quality Review",
        "core_content_en": (
            "Discussion on payment project end-to-end link integrity, exception fallback strategies and launch risks, "
            "covering payment gateway integration, order callbacks, refund security, reconciliation errors and stability readiness, "
            "forming test scope, risk checklist and launch acceptance conclusions."
        ),
    },
    {
        "id": "hr_recruit",
        "industry": "人力资源与招聘",
        "label": "人力资源与招聘｜招聘补岗",
        "scenario": "招聘补岗策略与渠道讨论",
        "core_content": (
            "围绕岗位缺口分析、候选人画像定义、招聘渠道策略和到岗时间压力展开讨论，"
            "明确补岗优先级、招聘策略和推进节奏"
        ),
        "scenario_en": "Recruitment Gap-Filling Strategy and Channel Discussion",
        "core_content_en": (
            "Discussion on headcount gap analysis, candidate profile definition, recruitment channel strategy "
            "and onboarding deadline pressure, clarifying hiring priorities, sourcing strategy and execution pace."
        ),
    },
    {
        "id": "commercialization",
        "industry": "商业化",
        "label": "娱乐/媒体｜艺人商业化",
        "scenario": "艺人品牌商业化合作策略讨论",
        "core_content": (
            "围绕艺人商业定位、品牌匹配度、报价策略、执行风险和转化目标展开讨论，"
            "形成艺人商业化推进策略和合作判断"
        ),
        "scenario_en": "Artist Brand Commercialization Partnership Strategy Discussion",
        "core_content_en": (
            "Discussion on artist commercial positioning, brand fit assessment, pricing strategy, "
            "execution risks and conversion targets, forming artist commercialization strategy and partnership evaluation."
        ),
    },
    {
        "id": "construction",
        "industry": "建筑与工程行业",
        "label": "建筑与工程行业｜项目交付",
        "scenario": "建筑工程项目交付进度与风险讨论",
        "core_content": (
            "围绕项目交付进度、现场施工问题、成本控制、风险处理和验收节点展开讨论，"
            "形成项目交付问题清单和推进方案"
        ),
        "scenario_en": "Construction Project Delivery Progress and Risk Discussion",
        "core_content_en": (
            "Discussion on project delivery schedule, on-site construction issues, cost control, "
            "risk mitigation and acceptance milestones, forming a project delivery issue list and advancement plan."
        ),
    },
    {
        "id": "consulting",
        "industry": "咨询/专业服务",
        "label": "咨询/专业服务｜客户拓展",
        "scenario": "咨询公司客户拓展策略讨论",
        "core_content": (
            "围绕客户需求分析、方案切入点、关系推进策略、报价策略和交付匹配度展开讨论，"
            "形成客户拓展策略和具体推进计划"
        ),
        "scenario_en": "Consulting Firm Client Development Strategy Discussion",
        "core_content_en": (
            "Discussion on client needs analysis, solution entry points, relationship advancement strategy, "
            "pricing strategy and delivery fit, forming a client development strategy and concrete next steps."
        ),
    },
    {
        "id": "legal",
        "industry": "法律服务",
        "label": "法律服务｜法顾专项",
        "scenario": "法律顾问专项案件处理讨论",
        "core_content": (
            "围绕法律风险识别、证据梳理、方案设计、边界判断和执行安排展开讨论，"
            "形成案件处理路径和分工安排"
        ),
        "scenario_en": "Legal Counsel Special Case Handling Discussion",
        "core_content_en": (
            "Discussion on legal risk identification, evidence review, solution design, "
            "boundary judgments and execution arrangements, forming a case handling pathway and work division."
        ),
    },
    {
        "id": "finance",
        "industry": "金融/投资",
        "label": "金融/投资｜资产配置",
        "scenario": "投资组合资产配置策略讨论",
        "core_content": (
            "围绕配置目标设定、风险承受评估、资金安排、收益预期和再平衡策略展开讨论，"
            "形成明确的资产配置建议和风险揭示"
        ),
        "scenario_en": "Investment Portfolio Asset Allocation Strategy Discussion",
        "core_content_en": (
            "Discussion on allocation objective setting, risk tolerance assessment, fund arrangement, "
            "return expectations and rebalancing strategy, forming clear asset allocation recommendations and risk disclosures."
        ),
    },
    {
        "id": "retail",
        "industry": "零售行业",
        "label": "零售行业｜会员复购",
        "scenario": "会员复购提升策略讨论",
        "core_content": (
            "围绕会员分层运营、促销活动策略、复购触达方式、门店协同和效果核查展开讨论，"
            "形成会员复购提升方案和执行节奏"
        ),
        "scenario_en": "Member Repurchase Enhancement Strategy Discussion",
        "core_content_en": (
            "Discussion on member tiered operations, promotional activity strategy, repurchase outreach methods, "
            "store coordination and performance verification, forming a member repurchase improvement plan and execution cadence."
        ),
    },
    {
        "id": "insurance",
        "industry": "保险行业",
        "label": "保险行业｜保险质检",
        "scenario": "保险销售质检问题复盘",
        "core_content": (
            "围绕录音质检结果、销售话术合规风险、培训改善计划和问题闭环机制展开讨论，"
            "形成质检结论和改善行动"
        ),
        "scenario_en": "Insurance Sales Quality Inspection Problem Review",
        "core_content_en": (
            "Discussion on call recording quality inspection results, sales script compliance risks, "
            "training improvement plans and issue closure mechanisms, forming quality inspection conclusions and improvement actions."
        ),
    },
    {
        "id": "medical",
        "industry": "医疗行业",
        "label": "医疗健康｜慢病随访",
        "scenario": "慢病患者随访沟通",
        "core_content": (
            "围绕患者症状变化、用药依从性、复诊安排、风险预警和患者配合度展开真实对话，"
            "形成随访安排、复查节点和注意事项"
        ),
        "scenario_en": "Chronic Disease Patient Follow-up Communication",
        "core_content_en": (
            "Genuine conversation around patient symptom changes, medication compliance, follow-up appointment scheduling, "
            "risk alerts and patient cooperation, forming clear follow-up arrangements, check-up milestones and precautions."
        ),
    },
    {
        "id": "realestate",
        "industry": "房地产",
        "label": "房地产｜项目去化",
        "scenario": "房产项目去化策略与渠道讨论",
        "core_content": (
            "围绕库存压力分析、客源结构、渠道效能提升、定价策略和售楼处转化率展开讨论，"
            "形成去化改善方案和近期行动"
        ),
        "scenario_en": "Real Estate Project Inventory Clearance Strategy and Channel Discussion",
        "core_content_en": (
            "Discussion on inventory pressure analysis, buyer source structure, channel efficiency improvement, "
            "pricing strategy and sales site conversion rate, forming an inventory clearance improvement plan and short-term actions."
        ),
    },
    {
        "id": "manufacturing",
        "industry": "制造业",
        "label": "制造业｜产线提效",
        "scenario": "制造业产线效率提升讨论",
        "core_content": (
            "围绕产线瓶颈识别、设备效能优化、良品率波动分析、排产协同和异常处理机制展开讨论，"
            "形成产线改善方案和重点改善行动"
        ),
        "scenario_en": "Manufacturing Production Line Efficiency Improvement Discussion",
        "core_content_en": (
            "Discussion on production line bottleneck identification, equipment efficiency optimization, yield fluctuation analysis, "
            "production scheduling coordination and anomaly handling mechanisms, "
            "forming a production line improvement plan and key improvement actions."
        ),
    },
]


# ─── Google Translate ───────────────────────────────────────────────────────

def _cjk_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\u4e00" <= c <= "\u9fff") / len(chars)


def _normalize_speaker_labels(text: str) -> str:
    """
    After translation, speaker labels get translated too (e.g. "Intervenant 1 :" in French).
    Normalize any "word(s) + N + colon" pattern at line start back to "Speaker N:".
    Handles non-breaking spaces (\xa0) that Google Translate injects around colons.
    """
    # Match translated speaker labels: one or more words, then a digit, then colon/spaces
    return re.sub(
        r"^[A-Za-zÀ-ÿäöüÄÖÜß\s\xa0]+?\s*(\d+)\s*[\xa0\s]*:\s*",
        r"Speaker \1: ",
        text,
        flags=re.MULTILINE,
    )


def _translate_chunk(chunk: str, target_lang: str) -> str:
    data = {"client": "gtx", "sl": "auto", "tl": target_lang, "dt": "t", "q": chunk}
    for attempt in range(6):
        try:
            resp = requests.post(_GT_URL, data=data, proxies=_NO_PROXY, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            translated = "".join(item[0] for item in result[0] if item[0])
            translated = _normalize_speaker_labels(translated)
            return translated
        except Exception as exc:
            if "429" in str(exc):
                wait = 60 * (attempt + 1)
                _log(f"  [translate] 429 rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                _log(f"  [translate] attempt {attempt+1} failed: {exc}")
                time.sleep(5)
    return chunk  # return original if all retries fail


def _translate_text(text: str, target_lang: str) -> str:
    """Split Chinese dialogue into safe chunks and translate each one."""
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current and current_len + line_len > _GT_CHUNK:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        chunks.append("\n".join(current))

    parts: list[str] = []
    for chunk in chunks:
        if _cjk_ratio(chunk) < 0.1:
            parts.append(chunk)
        else:
            parts.append(_translate_chunk(chunk, target_lang))
            time.sleep(2.0)  # respect rate limit
    return "\n".join(parts)


# ─── Quality check ──────────────────────────────────────────────────────────

def _passes_quality(text: str, lang_short: str) -> tuple[bool, str]:
    if not text or len(text) < MIN_CHARS:
        return False, f"too short ({len(text)} chars)"
    sample = text[:2000]
    cjk = _cjk_ratio(sample)
    if lang_short != "yue" and cjk > MAX_CJK_RATIO:
        return False, f"CJK ratio {cjk:.2f} > {MAX_CJK_RATIO}"
    lines = [l for l in sample.splitlines() if l.strip()]
    contents = [re.sub(r"^(Speaker|说話人)\s*\d+:\s*", "", l).strip() for l in lines]
    if contents:
        top_count = Counter(contents).most_common(1)[0][1]
        if top_count > MAX_REPEAT:
            return False, f"top line repeated {top_count}x"
    return True, ""


# ─── API call ───────────────────────────────────────────────────────────────

def _generate_chinese(template: dict, speaker_count: int) -> str:
    """Generate dialogue in Chinese (reliable path), return raw Chinese text."""
    payload = {
        "scenario":       template["scenario"],
        "core_content":   template["core_content"],
        "people_count":   speaker_count,
        "word_count":     WC_TARGET,
        "audio_language": "Chinese",
        "language":       "Chinese",
        "template_label": template["label"],
        "title":          template["scenario"],
        "tags":           ["training", "multilang_wc5000", template["id"]],
        "folder":         "training_long_dialogue",
        "profile": {
            "job_function": template["industry"],
            "work_content": template["scenario"],
            "use_case":     f"{template['industry']}｜{template['label'].split('｜')[-1]}",
        },
        "generation_context": {
            "domain":      template["industry"],
            "scene_type":  template["label"].split("｜")[-1],
            "scene_goal":  template["scenario"],
            "deliverable": template["core_content"],
        },
    }
    resp = requests.post(
        f"{BASE_URL}/api/generate_text",
        json=payload,
        timeout=180,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("dialogue_text") or data.get("text") or "").strip()


def _generate_cantonese(template: dict, speaker_count: int) -> str:
    """Generate Cantonese dialogue natively."""
    payload = {
        "scenario":       template["scenario_en"],
        "core_content":   template["core_content_en"],
        "people_count":   speaker_count,
        "word_count":     WC_TARGET,
        "audio_language": "Cantonese",
        "language":       "Cantonese",
        "template_label": template["label"],
        "title":          template["scenario_en"],
        "tags":           ["training", "multilang_wc5000", template["id"], "cantonese"],
        "folder":         "training_long_dialogue",
        "profile": {
            "job_function": template["industry"],
            "work_content": template["scenario_en"],
            "use_case":     f"{template['industry']}｜{template['label'].split('｜')[-1]}",
        },
        "generation_context": {
            "domain":      template["industry"],
            "scene_type":  template["label"].split("｜")[-1],
            "scene_goal":  template["scenario_en"],
            "deliverable": template["core_content_en"],
        },
    }
    resp = requests.post(
        f"{BASE_URL}/api/generate_text",
        json=payload,
        timeout=180,
        proxies={"http": None, "https": None},
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("dialogue_text") or data.get("text") or "").strip()


# ─── Main ───────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    safe = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = [
        (tmpl, lang, spk)
        for tmpl in TEMPLATES
        for lang in LANGUAGES
        for spk  in SPEAKER_COUNTS
    ]
    total = len(jobs)

    _log(f"===== Multilingual training data (FR/DE/ES/PT/YUE) =====")
    _log(f"Strategy: FR/DE/ES/PT via Chinese+translate; YUE native")
    _log(f"Total jobs: {total}")
    _log("=" * 55)

    done = skip = fail = 0

    for i, (tmpl, lang, spk) in enumerate(jobs, 1):
        fname = f"{tmpl['id']}_{lang['short']}_spk{spk}_wc{WC_TARGET}.txt"
        path  = OUT_DIR / fname

        if path.exists():
            text = path.read_text(encoding="utf-8")
            ok, _ = _passes_quality(text, lang["short"])
            if ok:
                skip += 1
                _log(f"[{i}/{total}] SKIP  {fname}")
                continue

        _log(f"[{i}/{total}] {fname}")

        best_text = ""
        best_ok   = False

        for attempt in range(1, RETRY_TIMES + 1):
            try:
                if lang["use_translate"]:
                    # Generate Chinese, then translate to target language
                    zh_text = _generate_chinese(tmpl, spk)
                    if not zh_text:
                        _log(f"  attempt {attempt} FAIL: empty Chinese generation")
                        time.sleep(RETRY_SLEEP)
                        continue
                    _log(f"  attempt {attempt} zh={len(zh_text)}c, translating to {lang['short']}...")
                    text = _translate_text(zh_text, lang["gt_code"])
                else:
                    text = _generate_cantonese(tmpl, spk)

            except Exception as exc:
                _log(f"  attempt {attempt} error: {exc}")
                time.sleep(RETRY_SLEEP)
                continue

            ok, fail_reason = _passes_quality(text, lang["short"])
            if ok:
                best_text = text
                best_ok   = True
                _log(f"  attempt {attempt} PASS ({len(text)} chars)")
                break
            else:
                _log(f"  attempt {attempt} FAIL: {fail_reason}")
                if len(text) > len(best_text):
                    best_text = text
                time.sleep(RETRY_SLEEP)

        if best_text:
            path.write_text(best_text, encoding="utf-8")
            status = "SAVED (OK)" if best_ok else f"SAVED (marginal)"
            _log(f"  -> {status}")
            done += 1 if best_ok else 0
            fail += 0 if best_ok else 1
        else:
            _log(f"  -> SKIPPED (no usable text)")
            fail += 1

        time.sleep(INTER_SLEEP)

    _log("=" * 55)
    _log(f"Done={done}  Marginal={fail}  Skipped={skip}")
    _log("Coverage:")
    for lang in LANGUAGES:
        files = list(OUT_DIR.glob(f"*_{lang['short']}_*_wc{WC_TARGET}.txt"))
        passed = sum(
            1 for p in files
            if _passes_quality(p.read_text(encoding="utf-8"), lang["short"])[0]
        )
        _log(f"  {lang['display']}: {passed}/{len(files)} pass")


if __name__ == "__main__":
    main()
