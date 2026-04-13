#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multilingual training data generation — FR / DE / ES / PT / YUE
=================================================================
Strategy:
  - FR / DE / ES / PT: Translate existing English wc5000 files using
    deep-translator (GoogleTranslator). This avoids re-generating content
    and produces clean target-language dialogue from already-good English files.
  - YUE (Cantonese): Generate natively via /api/generate_text since Cantonese
    uses CJK script and the LLM can produce it when prompted.

Generation matrix:
  14 templates × 5 languages × 5 speaker counts = 350 files

Usage:
  cd D:/ui_auto_test/demo_app
  python tools/generation/batch_multilang_training.py
"""

import re
import sys
import requests
import time
import random
from pathlib import Path
from datetime import datetime
from collections import Counter

try:
    from deep_translator import GoogleTranslator
    _HAS_DEEP_TRANSLATOR = True
except ImportError:
    _HAS_DEEP_TRANSLATOR = False
    print("WARNING: deep_translator not installed. Run: pip install deep-translator")

# ─── Config ────────────────────────────────────────────────────────────────
BASE_URL       = "http://127.0.0.1:8899"
OUT_DIR        = Path(__file__).resolve().parent.parent.parent / "demo" / "training_long_dialogue"
WC_TARGET      = 5000
RETRY_TIMES    = 3
INTER_SLEEP    = 4       # seconds between jobs
CHUNK_SLEEP    = 1.5     # seconds between translation chunks
MAX_CJK_RATIO  = 0.05
MAX_REPEAT     = 4
MIN_CHARS      = 2000

SPEAKER_COUNTS = [2, 3, 4, 5, 6]

LANGUAGES = [
    {"short": "fr",  "backend": "French",     "display": "法语",     "gt_code": "fr",  "use_translate": True},
    {"short": "de",  "backend": "German",     "display": "德语",     "gt_code": "de",  "use_translate": True},
    {"short": "es",  "backend": "Spanish",    "display": "西班牙语", "gt_code": "es",  "use_translate": True},
    {"short": "pt",  "backend": "Portuguese", "display": "葡萄牙语", "gt_code": "pt",  "use_translate": True},
    {"short": "yue", "backend": "Cantonese",  "display": "粤语",     "gt_code": None,  "use_translate": False},
]

TEMPLATES = [
    {"id": "ai_tech",          "industry": "人工智能/科技",   "label": "人工智能/科技｜付费转化",
     "scenario": "AI产品付费转化策略讨论",
     "core_content": "围绕付费转化漏斗优化、付费门槛设计与试用策略展开深度讨论，分析数据回收方式和用户价值感知提升方案",
     "scenario_en": "AI Product Paid Conversion Strategy Discussion",
     "core_content_en": "In-depth discussion on optimizing paid conversion funnels, payment threshold design and free-trial strategies."},
    {"id": "media_strategy",   "industry": "娱乐/媒体",       "label": "娱乐/媒体｜战略周会",
     "scenario": "娱乐媒体公司战略周会讨论",
     "core_content": "围绕业务目标进展、资源投入分配、重点风险识别和下周行动计划展开讨论",
     "scenario_en": "Entertainment Media Company Strategic Weekly Meeting",
     "core_content_en": "Discussion on business objective progress, resource allocation decisions, key risk identification."},
    {"id": "test_dev",         "industry": "测试开发",         "label": "测试开发｜支付项目",
     "scenario": "支付项目测试质量复盘",
     "core_content": "围绕支付项目的链路完整性、异常兜底策略和上线风险展开讨论",
     "scenario_en": "Payment Project Test Quality Review",
     "core_content_en": "Discussion on payment project end-to-end link integrity, exception fallback strategies and launch risks."},
    {"id": "hr_recruit",       "industry": "人力资源与招聘",   "label": "人力资源与招聘｜招聘补岗",
     "scenario": "招聘补岗策略与渠道讨论",
     "core_content": "围绕岗位缺口分析、候选人画像定义、招聘渠道策略和到岗时间压力展开讨论",
     "scenario_en": "Recruitment Gap-Filling Strategy and Channel Discussion",
     "core_content_en": "Discussion on headcount gap analysis, candidate profile definition, recruitment channel strategy."},
    {"id": "commercialization","industry": "商业化",           "label": "娱乐/媒体｜艺人商业化",
     "scenario": "艺人品牌商业化合作策略讨论",
     "core_content": "围绕艺人商业定位、品牌匹配度、报价策略、执行风险和转化目标展开讨论",
     "scenario_en": "Artist Brand Commercialization Partnership Strategy Discussion",
     "core_content_en": "Discussion on artist commercial positioning, brand fit assessment, pricing strategy."},
    {"id": "construction",     "industry": "建筑与工程行业",   "label": "建筑与工程行业｜项目交付",
     "scenario": "建筑工程项目交付进度与风险讨论",
     "core_content": "围绕项目交付进度、现场施工问题、成本控制、风险处理和验收节点展开讨论",
     "scenario_en": "Construction Project Delivery Progress and Risk Discussion",
     "core_content_en": "Discussion on project delivery schedule, on-site construction issues, cost control."},
    {"id": "consulting",       "industry": "咨询/专业服务",   "label": "咨询/专业服务｜客户拓展",
     "scenario": "咨询公司客户拓展策略讨论",
     "core_content": "围绕客户需求分析、方案切入点、关系推进策略、报价策略和交付匹配度展开讨论",
     "scenario_en": "Consulting Firm Client Development Strategy Discussion",
     "core_content_en": "Discussion on client needs analysis, solution entry points, relationship advancement strategy."},
    {"id": "legal",            "industry": "法律服务",         "label": "法律服务｜法顾专项",
     "scenario": "法律顾问专项案件处理讨论",
     "core_content": "围绕法律风险识别、证据梳理、方案设计、边界判断和执行安排展开讨论",
     "scenario_en": "Legal Counsel Special Case Handling Discussion",
     "core_content_en": "Discussion on legal risk identification, evidence review, solution design."},
    {"id": "finance",          "industry": "金融/投资",         "label": "金融/投资｜资产配置",
     "scenario": "投资组合资产配置策略讨论",
     "core_content": "围绕配置目标设定、风险承受评估、资金安排、收益预期和再平衡策略展开讨论",
     "scenario_en": "Investment Portfolio Asset Allocation Strategy Discussion",
     "core_content_en": "Discussion on allocation objective setting, risk tolerance assessment, fund arrangement."},
    {"id": "retail",           "industry": "零售行业",         "label": "零售行业｜会员复购",
     "scenario": "会员复购提升策略讨论",
     "core_content": "围绕会员分层运营、促销活动策略、复购触达方式、门店协同和效果核查展开讨论",
     "scenario_en": "Member Repurchase Enhancement Strategy Discussion",
     "core_content_en": "Discussion on member tiered operations, promotional activity strategy, repurchase outreach methods."},
    {"id": "insurance",        "industry": "保险行业",         "label": "保险行业｜保险质检",
     "scenario": "保险销售质检问题复盘",
     "core_content": "围绕录音质检结果、销售话术合规风险、培训改善计划和问题闭环机制展开讨论",
     "scenario_en": "Insurance Sales Quality Inspection Problem Review",
     "core_content_en": "Discussion on call recording quality inspection results, sales script compliance risks."},
    {"id": "medical",          "industry": "医疗行业",         "label": "医疗健康｜慢病随访",
     "scenario": "慢病患者随访沟通",
     "core_content": "围绕患者症状变化、用药依从性、复诊安排、风险预警和患者配合度展开真实对话",
     "scenario_en": "Chronic Disease Patient Follow-up Communication",
     "core_content_en": "Genuine conversation around patient symptom changes, medication compliance, follow-up scheduling."},
    {"id": "realestate",       "industry": "房地产",           "label": "房地产｜项目去化",
     "scenario": "房产项目去化策略与渠道讨论",
     "core_content": "围绕库存压力分析、客源结构、渠道效能提升、定价策略和售楼处转化率展开讨论",
     "scenario_en": "Real Estate Project Inventory Clearance Strategy and Channel Discussion",
     "core_content_en": "Discussion on inventory pressure analysis, buyer source structure, channel efficiency improvement."},
    {"id": "manufacturing",    "industry": "制造业",           "label": "制造业｜产线提效",
     "scenario": "制造业产线效率提升讨论",
     "core_content": "围绕产线瓶颈识别、设备效能优化、良品率波动分析、排产协同和异常处理机制展开讨论",
     "scenario_en": "Manufacturing Production Line Efficiency Improvement Discussion",
     "core_content_en": "Discussion on production line bottleneck identification, equipment efficiency optimization."},
]


# ─── Quality check ──────────────────────────────────────────────────────────

def _cjk_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\u4e00" <= c <= "\u9fff") / len(chars)


def _passes_quality(text: str, lang_short: str) -> tuple[bool, str]:
    if not text or len(text) < MIN_CHARS:
        return False, f"too short ({len(text)} chars)"
    sample = text[:3000]
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


# ─── Translation via deep_translator ────────────────────────────────────────

def _normalize_speaker_labels(text: str) -> str:
    """Re-normalize translated speaker labels (e.g. 'Sprecher 1:') back to 'Speaker N:'."""
    return re.sub(
        r"^[A-Za-z\xc0-\xff\xc0-\xd6\xd8-\xf6\xf8-\xff\-\s\xa0]+?\s*(\d+)\s*[\xa0\s]*[:\uff1a]\s*",
        r"Speaker \1: ",
        text,
        flags=re.MULTILINE,
    )


def _translate_text(text: str, target_lang: str) -> str:
    """
    Translate text to target_lang using deep_translator GoogleTranslator.
    Splits into ~4500-char chunks to stay within API limits.
    """
    if not _HAS_DEEP_TRANSLATOR:
        return text

    CHUNK_SIZE = 4500
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current = ""
    for line in lines:
        if len(current) + len(line) > CHUNK_SIZE and current:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)

    results: list[str] = []
    for i, chunk in enumerate(chunks):
        for attempt in range(4):
            try:
                translator = GoogleTranslator(source="auto", target=target_lang)
                translated = translator.translate(chunk)
                if translated:
                    results.append(_normalize_speaker_labels(translated))
                    break
            except Exception as exc:
                wait = 15 * (attempt + 1) + random.uniform(0, 5)
                _log(f"  [translate chunk {i+1}/{len(chunks)}] attempt {attempt+1} failed: {exc} — wait {wait:.0f}s")
                time.sleep(wait)
        else:
            results.append(chunk)  # keep original if all retries fail
        if i < len(chunks) - 1:
            time.sleep(CHUNK_SLEEP + random.uniform(0, 1))

    return "".join(results)


# ─── Cantonese native generation ────────────────────────────────────────────

def _generate_cantonese(template: dict, speaker_count: int) -> str:
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
    resp = requests.post(f"{BASE_URL}/api/generate_text", json=payload,
                         timeout=180, proxies={"http": None, "https": None})
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

    _log("===== Multilingual training data (FR/DE/ES/PT/YUE) =====")
    _log("Strategy: FR/DE/ES/PT translate from EN source; YUE native")
    _log(f"Total jobs: {total}")
    _log("=" * 55)

    done = skip = fail = 0

    for i, (tmpl, lang, spk) in enumerate(jobs, 1):
        fname = f"{tmpl['id']}_{lang['short']}_spk{spk}_wc{WC_TARGET}.txt"
        path  = OUT_DIR / fname

        # Skip if already good quality
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8")
                ok, _ = _passes_quality(text, lang["short"])
                if ok:
                    skip += 1
                    _log(f"[{i}/{total}] SKIP  {fname}")
                    continue
            except Exception:
                pass

        _log(f"[{i}/{total}] {fname}")

        best_text = ""
        best_ok   = False

        for attempt in range(1, RETRY_TIMES + 1):
            try:
                if lang["use_translate"]:
                    # Source: use the matching English training file
                    en_path = OUT_DIR / f"{tmpl['id']}_en_spk{spk}_wc{WC_TARGET}.txt"
                    if not en_path.exists():
                        _log(f"  source EN file missing: {en_path.name}, skipping")
                        break
                    en_text = en_path.read_text(encoding="utf-8")
                    _log(f"  attempt {attempt}: translating {len(en_text)}c EN → {lang['short']}...")
                    text = _translate_text(en_text, lang["gt_code"])
                else:
                    text = _generate_cantonese(tmpl, spk)

            except Exception as exc:
                _log(f"  attempt {attempt} error: {exc}")
                time.sleep(10)
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
                time.sleep(8)

        if best_text:
            path.write_text(best_text, encoding="utf-8")
            _log(f"  -> {'SAVED OK' if best_ok else 'SAVED marginal'}")
            if best_ok:
                done += 1
            else:
                fail += 1
        else:
            _log(f"  -> SKIPPED")
            fail += 1

        time.sleep(INTER_SLEEP + random.uniform(0, 2))

    _log("=" * 55)
    _log(f"Done={done}  Marginal={fail}  Skipped={skip}")
    _log("Coverage:")
    for lang in LANGUAGES:
        files = list(OUT_DIR.glob(f"*_{lang['short']}_*_wc{WC_TARGET}.txt"))
        passed = sum(
            1 for p in files
            if _passes_quality(p.read_text(encoding="utf-8"), lang["short"])[0]
        )
        _log(f"  {lang['display']}: {passed}/{len(files)} pass (target 70)")


if __name__ == "__main__":
    main()
