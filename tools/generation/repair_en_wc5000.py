#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
English wc5000 training data repair
=====================================
Regenerates the 66 failing English wc5000 training files that contain
repetitive fallback content (top line appears > 4 times).

Only overwrites files that fail quality check; passes are left untouched.

Usage:
  cd D:/ui_auto_test/audio-synthesis-demo
  python tools/generation/repair_en_wc5000.py
"""

import re
import requests
import time
from pathlib import Path
from datetime import datetime
from collections import Counter

# ─── Config ────────────────────────────────────────────────────────────────
BASE_URL        = "http://127.0.0.1:8899"
OUT_DIR         = Path(__file__).resolve().parent.parent.parent / "demo" / "training_long_dialogue"
MAX_CJK_RATIO   = 0.05
MAX_REPEAT      = 4
MAX_RETRIES     = 3
RETRY_SLEEP     = 8
INTER_SLEEP     = 3
WC_TARGET       = 5000
SPEAKER_COUNTS  = [2, 3, 4, 5, 6]

# ─── Templates (English only) ──────────────────────────────────────────────
TEMPLATES = [
    {
        "id": "ai_tech",
        "industry": "人工智能/科技",
        "label": "人工智能/科技｜付费转化",
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
        "scenario_en": "Manufacturing Production Line Efficiency Improvement Discussion",
        "core_content_en": (
            "Discussion on production line bottleneck identification, equipment efficiency optimization, yield fluctuation analysis, "
            "production scheduling coordination and anomaly handling mechanisms, "
            "forming a production line improvement plan and key improvement actions."
        ),
    },
]


# ─── Quality check ──────────────────────────────────────────────────────────

def _cjk_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\u4e00" <= c <= "\u9fff") / len(chars)


def _passes_quality(text: str) -> tuple[bool, str]:
    """Returns (passes, reason_if_failed)."""
    if not text or len(text) < 200:
        return False, f"too short ({len(text)} chars)"
    sample = text[:2000]
    cjk = _cjk_ratio(sample)
    if cjk > MAX_CJK_RATIO:
        return False, f"CJK ratio {cjk:.2f} > {MAX_CJK_RATIO}"
    lines = [l for l in sample.splitlines() if l.strip()]
    contents = [re.sub(r"^(Speaker|说話人)\s*\d+:\s*", "", l).strip() for l in lines]
    if contents:
        top_count = Counter(contents).most_common(1)[0][1]
        if top_count > MAX_REPEAT:
            top_line = Counter(contents).most_common(1)[0][0]
            return False, f"top line repeated {top_count}x: {top_line[:60]!r}"
    return True, ""


# ─── API call ───────────────────────────────────────────────────────────────

def _generate(template: dict, speaker_count: int) -> str:
    scenario     = template["scenario_en"]
    core_content = template["core_content_en"]
    payload = {
        "scenario":       scenario,
        "core_content":   core_content,
        "people_count":   speaker_count,
        "word_count":     WC_TARGET,
        "audio_language": "English",
        "language":       "English",
        "template_label": template["label"],
        "title":          scenario,
        "tags":           ["training", "repair_en_wc5000", template["id"]],
        "folder":         "training_long_dialogue",
        "profile": {
            "job_function": template["industry"],
            "work_content": scenario,
            "use_case":     f"{template['industry']}｜{template['label'].split('｜')[-1]}",
        },
        "generation_context": {
            "domain":      template["industry"],
            "scene_type":  template["label"].split("｜")[-1],
            "scene_goal":  scenario,
            "deliverable": core_content,
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

    # Build job list: only files that currently fail quality check
    jobs = []
    for tmpl in TEMPLATES:
        for spk in SPEAKER_COUNTS:
            fname = f"{tmpl['id']}_en_spk{spk}_wc{WC_TARGET}.txt"
            path  = OUT_DIR / fname
            if path.exists():
                text = path.read_text(encoding="utf-8")
                ok, reason = _passes_quality(text)
                if ok:
                    continue  # already good
                jobs.append((tmpl, spk, path, reason))
            else:
                jobs.append((tmpl, spk, path, "missing"))

    _log(f"===== English wc5000 repair =====")
    _log(f"Files needing repair: {len(jobs)}")
    _log("=" * 40)

    done = skip = fail = 0

    for i, (tmpl, spk, path, reason) in enumerate(jobs, 1):
        name = path.name
        _log(f"[{i}/{len(jobs)}] {name}  (reason: {reason})")

        best_text = ""
        best_ok   = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                text = _generate(tmpl, spk)
            except Exception as exc:
                _log(f"  attempt {attempt}/{MAX_RETRIES} API error: {exc}")
                time.sleep(RETRY_SLEEP)
                continue

            ok, fail_reason = _passes_quality(text)
            if ok:
                best_text = text
                best_ok   = True
                _log(f"  attempt {attempt} PASS ({len(text)} chars)")
                break
            else:
                _log(f"  attempt {attempt} FAIL: {fail_reason}")
                if len(text) > len(best_text):
                    best_text = text  # keep longest even if imperfect
                time.sleep(RETRY_SLEEP)

        if best_text:
            path.write_text(best_text, encoding="utf-8")
            if best_ok:
                _log(f"  -> SAVED (quality OK)")
                done += 1
            else:
                _log(f"  -> SAVED (best of {MAX_RETRIES} attempts, quality still marginal)")
                fail += 1
        else:
            _log(f"  -> SKIPPED (no usable text generated)")
            fail += 1

        time.sleep(INTER_SLEEP)

    _log("=" * 40)
    _log(f"Done={done}  Marginal={fail}  Skipped={skip}")

    # Final audit
    passed_after = sum(
        1 for tmpl in TEMPLATES for spk in SPEAKER_COUNTS
        if (OUT_DIR / f"{tmpl['id']}_en_spk{spk}_wc{WC_TARGET}.txt").exists()
        and _passes_quality(
            (OUT_DIR / f"{tmpl['id']}_en_spk{spk}_wc{WC_TARGET}.txt")
            .read_text(encoding="utf-8")
        )[0]
    )
    _log(f"Quality audit after repair: {passed_after}/70 pass")


if __name__ == "__main__":
    main()
