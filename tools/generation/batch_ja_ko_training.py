#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日语/韩语训练数据批量生成
==============================
生成矩阵：
  - 14 个行业模板
  - 2  种语言：日语 / 韩语
  - 5  种说话人数：2 / 3 / 4 / 5 / 6
  - 6  个字数档位：5000 / 10000 / 20000 / 30000 / 40000 / 50000
  = 14 × 2 × 5 × 6 = 840 个训练文件

策略：
  scenario / core_content 用英文原生内容，language 参数传 "Japanese"/"Korean"
  LLM 直接生成目标语言对话，无需二次翻译
  few_shot_selector 已扩展支持 ja / ko 映射

用法：
  cd D:/ui_auto_test/audio-synthesis-demo
  python tools/generation/batch_ja_ko_training.py
"""

import requests
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta

# ─── 配置 ──────────────────────────────────────────────────────────────────
BASE_URL           = "http://127.0.0.1:8899"
OUT_DIR            = Path(__file__).resolve().parent.parent.parent / "demo" / "training_long_dialogue"
CHARS_PER_SEGMENT  = 3000
MAX_CHARS_TARGET   = 51000
RETRY_TIMES        = 3
RETRY_SLEEP        = 8
INTER_CALL_SLEEP   = 2

WORD_COUNT_LEVELS  = [5000, 10000, 20000, 30000, 40000, 50000]

LANGUAGES = [
    {"short": "ja", "backend": "Japanese", "display": "日語"},
    {"short": "ko", "backend": "Korean",   "display": "한국어"},
]

SPEAKER_COUNTS = [2, 3, 4, 5, 6]

# ─── 14 个行业模板（使用英文 scenario/core_content 让 LLM 原生生成目标语言）──
TEMPLATES = [
    {
        "id":              "ai_tech",
        "industry":        "人工智能/科技",
        "label":           "人工智能/科技｜付费转化",
        "scenario":        "AI Product Paid Conversion Strategy Discussion",
        "core_content":    (
            "In-depth discussion on optimizing paid conversion funnels, payment threshold design and free-trial strategies, "
            "analyzing data collection methods and user value perception improvements, "
            "forming a paid conversion optimization plan and experiment roadmap."
        ),
    },
    {
        "id":              "media_strategy",
        "industry":        "娱乐/媒体",
        "label":           "娱乐/媒体｜战略周会",
        "scenario":        "Entertainment Media Company Strategic Weekly Meeting",
        "core_content":    (
            "Discussion on business objective progress, resource allocation decisions, key risk identification, "
            "and next-week action plans, forming key decisions and clear task assignments for the strategic weekly meeting."
        ),
    },
    {
        "id":              "test_dev",
        "industry":        "测试开发",
        "label":           "测试开发｜支付项目",
        "scenario":        "Payment Project Test Quality Review",
        "core_content":    (
            "Discussion on payment project end-to-end link integrity, exception fallback strategies and launch risks, "
            "covering payment gateway integration, order callbacks, refund security, reconciliation errors and stability readiness, "
            "forming test scope, risk checklist and launch acceptance conclusions."
        ),
    },
    {
        "id":              "hr_recruit",
        "industry":        "人力资源与招聘",
        "label":           "人力资源与招聘｜招聘补岗",
        "scenario":        "Recruitment Gap-Filling Strategy and Channel Discussion",
        "core_content":    (
            "Discussion on headcount gap analysis, candidate profile definition, recruitment channel strategy "
            "and onboarding deadline pressure, clarifying hiring priorities, sourcing strategy and execution pace."
        ),
    },
    {
        "id":              "commercialization",
        "industry":        "商业化",
        "label":           "娱乐/媒体｜艺人商业化",
        "scenario":        "Artist Brand Commercialization Partnership Strategy Discussion",
        "core_content":    (
            "Discussion on artist commercial positioning, brand fit assessment, pricing strategy, "
            "execution risks and conversion targets, forming artist commercialization strategy and partnership evaluation."
        ),
    },
    {
        "id":              "construction",
        "industry":        "建筑与工程行业",
        "label":           "建筑与工程行业｜项目交付",
        "scenario":        "Construction Project Delivery Progress and Risk Discussion",
        "core_content":    (
            "Discussion on project delivery schedule, on-site construction issues, cost control, "
            "risk mitigation and acceptance milestones, forming a project delivery issue list and advancement plan."
        ),
    },
    {
        "id":              "consulting",
        "industry":        "咨询/专业服务",
        "label":           "咨询/专业服务｜客户拓展",
        "scenario":        "Consulting Firm Client Development Strategy Discussion",
        "core_content":    (
            "Discussion on client needs analysis, solution entry points, relationship advancement strategy, "
            "pricing strategy and delivery fit, forming a client development strategy and concrete next steps."
        ),
    },
    {
        "id":              "legal",
        "industry":        "法律服务",
        "label":           "法律服务｜法顾专项",
        "scenario":        "Legal Counsel Special Case Handling Discussion",
        "core_content":    (
            "Discussion on legal risk identification, evidence review, solution design, "
            "boundary judgments and execution arrangements, forming a case handling pathway and work division."
        ),
    },
    {
        "id":              "finance",
        "industry":        "金融/投资",
        "label":           "金融/投资｜资产配置",
        "scenario":        "Investment Portfolio Asset Allocation Strategy Discussion",
        "core_content":    (
            "Discussion on allocation objective setting, risk tolerance assessment, fund arrangement, "
            "return expectations and rebalancing strategy, forming clear asset allocation recommendations and risk disclosures."
        ),
    },
    {
        "id":              "retail",
        "industry":        "零售行业",
        "label":           "零售行业｜会员复购",
        "scenario":        "Member Repurchase Enhancement Strategy Discussion",
        "core_content":    (
            "Discussion on member tiered operations, promotional activity strategy, repurchase outreach methods, "
            "store coordination and performance verification, forming a member repurchase improvement plan and execution cadence."
        ),
    },
    {
        "id":              "insurance",
        "industry":        "保险行业",
        "label":           "保险行业｜保险质检",
        "scenario":        "Insurance Sales Quality Inspection Problem Review",
        "core_content":    (
            "Discussion on call recording quality inspection results, sales script compliance risks, "
            "training improvement plans and issue closure mechanisms, forming quality inspection conclusions and improvement actions."
        ),
    },
    {
        "id":              "medical",
        "industry":        "医疗行业",
        "label":           "医疗健康｜慢病随访",
        "scenario":        "Chronic Disease Patient Follow-up Communication",
        "core_content":    (
            "Genuine conversation around patient symptom changes, medication compliance, follow-up appointment scheduling, "
            "risk alerts and patient cooperation, forming clear follow-up arrangements, check-up milestones and precautions."
        ),
    },
    {
        "id":              "realestate",
        "industry":        "房地产",
        "label":           "房地产｜项目去化",
        "scenario":        "Real Estate Project Inventory Clearance Strategy and Channel Discussion",
        "core_content":    (
            "Discussion on inventory pressure analysis, buyer source structure, channel efficiency improvement, "
            "pricing strategy and sales site conversion rate, forming an inventory clearance improvement plan and short-term actions."
        ),
    },
    {
        "id":              "manufacturing",
        "industry":        "制造业",
        "label":           "制造业｜产线提效",
        "scenario":        "Manufacturing Production Line Efficiency Improvement Discussion",
        "core_content":    (
            "Discussion on production line bottleneck identification, equipment efficiency optimization, yield fluctuation analysis, "
            "production scheduling coordination and anomaly handling mechanisms, "
            "forming a production line improvement plan and key improvement actions."
        ),
    },
]


# ─── 工具函数 ──────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    safe = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)


def generate_segment(template: dict, language_backend: str, speaker_count: int) -> str:
    payload = {
        "scenario":       template["scenario"],
        "core_content":   template["core_content"],
        "people_count":   speaker_count,
        "word_count":     3000,
        "audio_language": language_backend,
        "language":       language_backend,
        "title":          template["scenario"],
        "tags":           ["training", "long_dialogue", template["id"], language_backend.lower()],
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


def truncate_at_boundary(full_text: str, target_chars: int) -> str:
    if len(full_text) <= target_chars:
        return full_text
    lines = full_text.split("\n")
    result_lines, total = [], 0
    for line in lines:
        line_len = len(line) + 1
        if total + line_len > target_chars and result_lines:
            break
        result_lines.append(line)
        total += line_len
    return "\n".join(result_lines)


# ─── 主流程 ────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base_jobs = [
        (tmpl, lang, spk)
        for tmpl in TEMPLATES
        for lang in LANGUAGES
        for spk  in SPEAKER_COUNTS
    ]
    total_base  = len(base_jobs)
    total_files = total_base * len(WORD_COUNT_LEVELS)

    _log("===== 日语/韩语训练数据生成 =====")
    _log(f"Base jobs: {total_base} | Output files: {total_files}")
    _log(f"Output dir: {OUT_DIR}")
    _log("=" * 40)

    segments_per_job = -(-MAX_CHARS_TARGET // CHARS_PER_SEGMENT)
    started_at = time.time()
    done_jobs = skip_jobs = fail_jobs = 0

    for job_idx, (tmpl, lang, spk) in enumerate(base_jobs, 1):
        prefix = f"{tmpl['id']}_{lang['short']}_spk{spk}"
        all_paths = {
            wc: OUT_DIR / f"{prefix}_wc{wc}.txt"
            for wc in WORD_COUNT_LEVELS
        }

        if all(p.exists() for p in all_paths.values()):
            skip_jobs += 1
            _log(f"[{job_idx}/{total_base}] SKIP  {prefix}")
            continue

        _log(f"[{job_idx}/{total_base}] START {prefix}  "
             f"(行业={tmpl['industry']}, 语言={lang['display']}, 说话人={spk})")

        segments: list[str] = []
        total_chars = 0
        seg_num = 0
        fail_seg = 0

        while total_chars < MAX_CHARS_TARGET:
            seg_num += 1
            text = ""
            for retry in range(RETRY_TIMES):
                try:
                    text = generate_segment(tmpl, lang["backend"], spk)
                    if text:
                        break
                except Exception as exc:
                    _log(f"  片段 {seg_num} 第{retry+1}次失败: {exc}")
                    time.sleep(RETRY_SLEEP)

            if not text:
                fail_seg += 1
                _log(f"  片段 {seg_num} 全部重试失败，跳过此片段")
                if fail_seg >= 5:
                    _log(f"  连续失败过多，放弃 job {prefix}")
                    fail_jobs += 1
                    break
                continue

            fail_seg = 0
            segments.append(text)
            total_chars += len(text)
            _log(f"  片段 {seg_num}/{segments_per_job} +{len(text)}字 → 累计{total_chars}字")
            time.sleep(INTER_CALL_SLEEP)

        if total_chars == 0:
            continue

        full_text = "\n\n".join(segments)

        saved = []
        for wc in WORD_COUNT_LEVELS:
            out_path = all_paths[wc]
            if not out_path.exists():
                chunk = truncate_at_boundary(full_text, wc)
                out_path.write_text(chunk, encoding="utf-8")
                saved.append(f"wc{wc}({len(chunk)}字)")

        done_jobs += 1
        elapsed = time.time() - started_at
        eta_secs = (elapsed / done_jobs) * (total_base - job_idx) if done_jobs else 0
        _log(f"  ✓ 已保存: {', '.join(saved)}  "
             f"| 耗时 {elapsed/60:.1f}min | 预计剩余 {timedelta(seconds=int(eta_secs))}")

    elapsed_total = time.time() - started_at
    _log("=" * 40)
    _log(f"完成! 完成={done_jobs}, 跳过={skip_jobs}, 失败={fail_jobs}")
    _log(f"总耗时: {timedelta(seconds=int(elapsed_total))}")
    _log(f"输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
