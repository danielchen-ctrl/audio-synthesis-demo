#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_training_plan_jobs.py
============================
按 batch 名称生成训练方案 v2 的任务 JSONL 文件。

支持的 batch：
  b0_smoke               22 正配对 × 3语言 × [2,6,10]人 × [1000,10000,30000]字 × 1seed = 594
  b1_foundation          22 预置模板 × 3语言 × [2,4,6,8,10]人 × [1000,3000,5000,10000,20000,30000]字 × 2seed = 3960
  b2_positive_pairs      22 正配对 × 3语言 × [2..10]人 × [500,1000,3000,5000,10000,15000,20000,25000,30000]字 × 3seed = 16038
  b3_cross_combo_base    21主题×22模板 × 3语言 × [2,4,8]人 × [3000,10000,30000]字 × 2seed = 24948
  b4_high_risk_boost     105高风险组合 × 3语言 × [4,6,8,10]人 × [10000,15000,20000,25000,30000]字 × 3seed = 18900 (wait, actually: 105*3*4*5*3=18900... but let me check if we need seed count)
  b5_extreme_50k         66精选组合 × 3语言 × [4,8,10]人 × [50000]字 × 2seed = 1188 (wait: 66*3*3*1*2=1188)

用法：
  python tools/training/build_training_plan_jobs.py --batch b0_smoke
  python tools/training/build_training_plan_jobs.py --batch b0_smoke --out training/data/training_jobs_b0_smoke.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.plan_v2_data import (
    B4_RISK_PAIRINGS,
    B5_EXTREME_COMBOS,
    MANUAL_TOPICS,
    POSITIVE_PAIRS,
    PRESET_TEMPLATES,
    TEMPLATE_BY_ID,
    TOPIC_BY_ID,
    ManualTopic,
    PresetTemplate,
)
from training.translation_helpers import localize_profile_value, translate_scenario_and_core

# ─────────────────────────────────────────────────────
# 常量：训练方案 v2 各 Batch 参数
# ─────────────────────────────────────────────────────

PRIMARY_LANGUAGES = ["中文", "英语", "日语"]

BATCH_CONFIGS: Dict[str, Dict[str, Any]] = {
    "b0_smoke": {
        "desc": "B0 Smoke 验证批 (594 tasks)",
        "languages": PRIMARY_LANGUAGES,
        "people_counts": [2, 6, 10],
        "word_counts": [1000, 10000, 30000],
        "seeds": [42],
        "combo_source": "positive_pairs",
    },
    "b1_foundation": {
        "desc": "B1 模板底座训练 (3960 tasks)",
        "languages": PRIMARY_LANGUAGES,
        "people_counts": [2, 4, 6, 8, 10],
        "word_counts": [1000, 3000, 5000, 10000, 20000, 30000],
        "seeds": [101, 102],
        "combo_source": "templates_only",
    },
    "b2_positive_pairs": {
        "desc": "B2 正配对强化训练 (16038 tasks)",
        "languages": PRIMARY_LANGUAGES,
        "people_counts": [2, 3, 4, 5, 6, 7, 8, 9, 10],
        "word_counts": [500, 1000, 3000, 5000, 10000, 15000, 20000, 25000, 30000],
        "seeds": [201, 202, 203],
        "combo_source": "positive_pairs",
    },
    "b3_cross_combo_base": {
        "desc": "B3 全交叉基础覆盖 (24948 tasks)",
        "languages": PRIMARY_LANGUAGES,
        "people_counts": [2, 4, 8],
        "word_counts": [3000, 10000, 30000],
        "seeds": [301, 302],
        "combo_source": "all_cross",
    },
    "b4_high_risk_boost": {
        "desc": "B4 高风险泛化强化 (18900 tasks)",
        "languages": PRIMARY_LANGUAGES,
        "people_counts": [4, 6, 8, 10],
        "word_counts": [10000, 15000, 20000, 25000, 30000],
        "seeds": [401, 402, 403],
        "combo_source": "b4_risk",
    },
    "b5_extreme_50k": {
        "desc": "B5 50000字极限强化 (1188 tasks)",
        "languages": PRIMARY_LANGUAGES,
        "people_counts": [4, 8, 10],
        "word_counts": [50000],
        "seeds": [501, 502],
        "combo_source": "b5_extreme",
    },
}

# ─────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────

def _make_seed(topic_id: str, template_id: str, language: str, people: int, wc: int, seed_base: int) -> int:
    key = f"{topic_id}|{template_id}|{language}|{people}|{wc}|{seed_base}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) % (2**31)


def _select_work_content(industry: str) -> str:
    mapping = {
        "医疗健康": "医疗服务供应商",
        "人力资源与招聘": "招聘与人才获取",
        "娱乐/媒体": "内容制作",
        "建筑与工程行业": "工程规划与施工",
        "汽车行业": "整车制造",
        "咨询/专业服务": "管理咨询",
        "法律服务": "法务/合规",
        "金融/投资": "投资银行",
        "零售行业": "零售运营",
        "保险行业": "保险销售与理赔",
        "房地产": "房地产开发",
        "人工智能/科技": "产品研发",
        "制造业": "生产运营",
        "测试开发": "产品研发",
    }
    return mapping.get(industry, "综合管理")


def _select_seniority(people_count: int) -> str:
    if people_count >= 7:
        return "C层/创始人"
    if people_count >= 5:
        return "总监"
    if people_count >= 3:
        return "经理"
    return "主管"


def _build_job(
    topic: ManualTopic,
    template: PresetTemplate,
    language: str,
    people_count: int,
    word_count: int,
    seed: int,
    batch: str,
) -> Dict[str, Any]:
    """把一个 (topic, template, language, people, wc, seed) 组合转换为任务 dict。"""
    # scenario 和 core_content：直接使用模板内容（方案A：B1用模板自身，B2-B5用主题覆盖）
    # B1 (templates_only) 没有 topic，直接用模板文字
    # 其他 batch：scenario 来自 topic，但 core 来自 template（控制模板纯度）
    scenario_cn = template.scenario_cn
    core_cn = template.core_content_cn

    if topic is not None and batch != "b1_foundation":
        # 把手动主题的关键词注入到 scenario 开头，强化主题信号
        scenario_cn = f"【主题】{topic.topic_cn}\n{template.scenario_cn}"

    # 翻译
    scenario_text, core_text, fallback_used = translate_scenario_and_core(
        scenario_cn, core_cn, language
    )

    industry = template.industry
    work_content = _select_work_content(industry)
    seniority = _select_seniority(people_count)

    return {
        "job_function": localize_profile_value(industry, language),
        "work_content": localize_profile_value(work_content, language),
        "seniority": localize_profile_value(seniority, language),
        "scenario": scenario_text,
        "core_content": core_text,
        "language": language,
        "people_count": people_count,
        "word_count": word_count,
        "seed": seed,
        "meta": {
            "batch": batch,
            "topic_id": topic.topic_id if topic else None,
            "template_id": template.template_id,
            "template_name": template.name_cn,
            "topic_cn": topic.topic_cn if topic else None,
            "translate_fallback": fallback_used,
            "scenario_id": f"{batch}_{template.template_id}_{(topic.topic_id if topic else 'self')}",
        },
    }


# ─────────────────────────────────────────────────────
# 组合来源构建器
# ─────────────────────────────────────────────────────

def _get_combos(combo_source: str) -> List[Tuple[ManualTopic | None, PresetTemplate]]:
    """返回 (topic_or_None, template) 对列表。"""
    if combo_source == "positive_pairs":
        return [(TOPIC_BY_ID[tid], TEMPLATE_BY_ID[tmpl]) for tid, tmpl in POSITIVE_PAIRS]

    if combo_source == "templates_only":
        # B1: 模板自身，无手动主题
        return [(None, t) for t in PRESET_TEMPLATES]

    if combo_source == "all_cross":
        # B3: 21 手动主题 × 22 模板全交叉
        result = []
        for topic in MANUAL_TOPICS:
            for template in PRESET_TEMPLATES:
                result.append((topic, template))
        return result

    if combo_source == "b4_risk":
        return [(TOPIC_BY_ID[tid], TEMPLATE_BY_ID[tmpl]) for tid, tmpl in B4_RISK_PAIRINGS]

    if combo_source == "b5_extreme":
        return [(TOPIC_BY_ID[tid], TEMPLATE_BY_ID[tmpl]) for tid, tmpl in B5_EXTREME_COMBOS]

    raise ValueError(f"未知 combo_source: {combo_source}")


# ─────────────────────────────────────────────────────
# 主生成函数
# ─────────────────────────────────────────────────────

def build_jobs_for_batch(batch: str) -> List[Dict[str, Any]]:
    if batch not in BATCH_CONFIGS:
        raise ValueError(f"未知 batch: {batch}，可选: {list(BATCH_CONFIGS)}")

    cfg = BATCH_CONFIGS[batch]
    combos = _get_combos(cfg["combo_source"])
    jobs: List[Dict[str, Any]] = []

    for topic, template in combos:
        for language in cfg["languages"]:
            for people_count in cfg["people_counts"]:
                for word_count in cfg["word_counts"]:
                    for seed_base in cfg["seeds"]:
                        seed = _make_seed(
                            topic.topic_id if topic else template.template_id,
                            template.template_id,
                            language,
                            people_count,
                            word_count,
                            seed_base,
                        )
                        job = _build_job(
                            topic=topic,
                            template=template,
                            language=language,
                            people_count=people_count,
                            word_count=word_count,
                            seed=seed,
                            batch=batch,
                        )
                        jobs.append(job)

    return jobs


def write_jobs(jobs: List[Dict[str, Any]], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(json.dumps(job, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="生成训练方案 v2 任务 JSONL")
    parser.add_argument(
        "--batch",
        required=True,
        choices=list(BATCH_CONFIGS),
        help="训练批次名称",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="输出 JSONL 路径（默认：training/data/training_jobs_{batch}.jsonl）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印任务数量，不写文件",
    )
    args = parser.parse_args()

    cfg = BATCH_CONFIGS[args.batch]
    print(f"[build_training_plan_jobs] batch={args.batch}  {cfg['desc']}")

    jobs = build_jobs_for_batch(args.batch)
    print(f"  生成任务数: {len(jobs)}")

    if args.dry_run:
        print("  --dry-run 模式，不写文件")
        return

    out_path = args.out or str(ROOT / "training" / "data" / f"training_jobs_{args.batch}.jsonl")
    write_jobs(jobs, out_path)
    print(f"  写入: {out_path}")


if __name__ == "__main__":
    main()
