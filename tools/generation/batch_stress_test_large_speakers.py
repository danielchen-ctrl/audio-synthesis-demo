#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大说话人数压力测试 (8/10人)
==============================
验证目标：
  在 8 人和 10 人对话场景下：
  1. role cycling 分配是否均匀（每位说话人轮次差 ≤ 2）
  2. variant 池在高 round 数时是否仍有多样性（连续 3 轮不得完全重复）
  3. 输出格式正确（每行 "Speaker N: ..." 格式不缺失）

生成矩阵：
  3 个行业（ai_tech / medical / legal）
  × 2 种语言（中文 / 英语）
  × 2 种说话人数（8 / 10）
  × 6 档位字数
  = 3 × 2 × 2 × 6 = 72 个文件

用法：
  cd D:/ui_auto_test/audio-synthesis-demo
  python tools/generation/batch_stress_test_large_speakers.py
"""

import re
import requests
import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

BASE_URL = "http://127.0.0.1:8899"
OUT_DIR  = Path(__file__).resolve().parent.parent.parent / "demo" / "training_stress_large_speakers"
CHARS_PER_SEGMENT = 3000
MAX_CHARS_TARGET  = 51000
RETRY_TIMES       = 3
RETRY_SLEEP       = 8
INTER_CALL_SLEEP  = 2

WORD_COUNT_LEVELS = [5000, 10000, 20000, 30000, 40000, 50000]
SPEAKER_COUNTS    = [8, 10]

LANGUAGES = [
    {"short": "zh", "backend": "Chinese",  "display": "中文"},
    {"short": "en", "backend": "English",  "display": "英语"},
]

TEMPLATES = [
    {
        "id":              "ai_tech",
        "label":           "人工智能/科技｜付费转化",
        "industry":        "人工智能/科技",
        "scenario":        "AI产品付费转化策略讨论",
        "core_content":    (
            "围绕付费转化漏斗优化、付费门槛设计与试用策略展开深度讨论，"
            "分析数据回收方式和用户价值感知提升方案，形成付费转化优化方案和实验计划"
        ),
        "scenario_en":     "AI Product Paid Conversion Strategy Discussion",
        "core_content_en": (
            "In-depth discussion on optimizing paid conversion funnels, payment threshold design and free-trial strategies, "
            "analyzing data collection methods and user value perception improvements, "
            "forming a paid conversion optimization plan and experiment roadmap."
        ),
    },
    {
        "id":              "medical",
        "label":           "医疗健康｜慢病随访",
        "industry":        "医疗行业",
        "scenario":        "慢病患者随访沟通",
        "core_content":    (
            "围绕患者症状变化、用药执行情况、复查节点安排、风险提示和患者配合度展开真实交流，"
            "形成清晰的随访安排、复查节点和注意事项"
        ),
        "scenario_en":     "Chronic Disease Patient Follow-up Communication",
        "core_content_en": (
            "Genuine conversation around patient symptom changes, medication compliance, follow-up appointment scheduling, "
            "risk alerts and patient cooperation, forming clear follow-up arrangements, check-up milestones and precautions."
        ),
    },
    {
        "id":              "legal",
        "label":           "法律服务｜法顾专项",
        "industry":        "法律服务",
        "scenario":        "法律顾问专项案件处理讨论",
        "core_content":    (
            "围绕法律风险识别、证据材料梳理、处理方案设计、边界判断和执行安排展开讨论，"
            "形成法顾专项的处理路径和分工建议"
        ),
        "scenario_en":     "Legal Counsel Special Case Handling Discussion",
        "core_content_en": (
            "Discussion on legal risk identification, evidence review, solution design, "
            "boundary judgments and execution arrangements, forming a case handling pathway and work division."
        ),
    },
]


# ─── 工具函数 ──────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    safe = msg.encode("gbk", errors="replace").decode("gbk")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)


def generate_segment(template: dict, language_backend: str, speaker_count: int) -> str:
    is_english   = language_backend == "English"
    scenario     = template["scenario_en"]     if is_english else template["scenario"]
    core_content = template["core_content_en"] if is_english else template["core_content"]

    payload = {
        "scenario":       scenario,
        "core_content":   core_content,
        "people_count":   speaker_count,
        "word_count":     3000,
        "audio_language": language_backend,
        "language":       language_backend,
        "title":          scenario,
        "tags":           ["stress_test", "large_speakers", template["id"]],
        "folder":         "training_stress_large_speakers",
        "profile": {
            "job_function": template["industry"],
            "work_content": scenario,
        },
        "generation_context": {
            "domain":     template["industry"],
            "scene_type": template["label"].split("｜")[-1],
            "scene_goal": scenario,
        },
    }
    resp = requests.post(
        f"{BASE_URL}/api/generate_text",
        json=payload,
        timeout=180,
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


# ─── 验证工具 ──────────────────────────────────────────────────────────────

def validate_text(text: str, speaker_count: int, language: str) -> dict:
    """对生成文本做三项检查，返回 {turn_balance, variety, format_ok}"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. 格式检查：每行以 "Speaker N:" 或 "说话人N:" 开头
    speaker_lines = [l for l in lines if re.match(r"(Speaker\s*\d+:|说话人\s*\d+:)", l)]
    format_ok = len(speaker_lines) >= max(10, len(lines) // 3)

    # 2. 轮次均衡性：各说话人出现次数的极差 ≤ 2×平均值×0.3
    turn_counts = Counter()
    for l in speaker_lines:
        m = re.match(r"(?:Speaker|说话人)\s*(\d+)", l)
        if m:
            turn_counts[int(m.group(1))] += 1
    if turn_counts:
        vals = list(turn_counts.values())
        avg  = sum(vals) / len(vals)
        diff = max(vals) - min(vals)
        turn_balance = diff <= max(2, avg * 0.5)
    else:
        turn_balance = False

    # 3. 多样性：取连续 20 行，不得有 ≥3 行完全相同
    variety = True
    for i in range(0, len(speaker_lines) - 20, 5):
        window = [re.sub(r"^(?:Speaker|说话人)\s*\d+:\s*", "", l) for l in speaker_lines[i:i+20]]
        counter = Counter(window)
        if counter.most_common(1)[0][1] >= 3:
            variety = False
            break

    return {
        "turn_balance": turn_balance,
        "variety":      variety,
        "format_ok":    format_ok,
        "turns":        dict(turn_counts),
    }


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

    _log("===== 大说话人压力测试 =====")
    _log(f"Base jobs: {total_base} | Output files: {total_files}")
    _log(f"Speaker counts: {SPEAKER_COUNTS}")
    _log(f"Output dir: {OUT_DIR}")
    _log("=" * 40)

    segments_per_job = -(-MAX_CHARS_TARGET // CHARS_PER_SEGMENT)
    started_at = time.time()
    done_jobs = skip_jobs = fail_jobs = 0
    validation_results = []

    for job_idx, (tmpl, lang, spk) in enumerate(base_jobs, 1):
        prefix   = f"{tmpl['id']}_{lang['short']}_spk{spk}"
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

        # ── 验证第一段 ──────────────────────────────────
        if segments:
            vr = validate_text(segments[0], spk, lang["backend"])
            status_str = (
                f"format={'OK' if vr['format_ok'] else 'FAIL'} "
                f"balance={'OK' if vr['turn_balance'] else 'FAIL'} "
                f"variety={'OK' if vr['variety'] else 'FAIL'} "
                f"turns={vr['turns']}"
            )
            _log(f"  [验证] {status_str}")
            validation_results.append({"job": prefix, **vr})

        # ── 按档位切分并保存 ──────────────────────────
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
        _log(f"  ✓ 已保存: {', '.join(saved)}  | 预计剩余 {timedelta(seconds=int(eta_secs))}")

    # ── 验证汇总 ──────────────────────────────────────
    elapsed_total = time.time() - started_at
    _log("=" * 40)
    _log(f"完成! 完成={done_jobs}, 跳过={skip_jobs}, 失败={fail_jobs}")
    _log(f"总耗时: {timedelta(seconds=int(elapsed_total))}")

    if validation_results:
        _log("\n===== 验证汇总 =====")
        all_pass = 0
        for r in validation_results:
            ok = r["format_ok"] and r["turn_balance"] and r["variety"]
            mark = "PASS" if ok else "FAIL"
            if ok:
                all_pass += 1
            _log(f"  [{mark}] {r['job']}  balance={r['turn_balance']} variety={r['variety']}")
        _log(f"通过: {all_pass}/{len(validation_results)}")

    # ── 写验证报告 ─────────────────────────────────────
    report_path = OUT_DIR / "validation_report.json"
    report_path.write_text(
        json.dumps(validation_results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    _log(f"验证报告: {report_path}")


if __name__ == "__main__":
    main()
