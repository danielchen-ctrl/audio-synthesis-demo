#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.task_matrix_builder import build_tasks, write_jsonl
from training.training_executor import execute_tasks
from training.training_storage import TrainingStorage


def main() -> None:
    parser = argparse.ArgumentParser(description="按训练阶段执行统一训练计划")
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "foundation_templates",
            "manual_aligned",
            "cross_combo",
            "long_dialogue_special",
            "stress_large_speakers",
            "runtime_few_shot",
        ],
        help="训练阶段",
    )
    parser.add_argument("--task-jsonl", type=str, default="", help="可选：先把任务写到指定 JSONL")
    parser.add_argument("--storage-dir", type=str, default="output/training/unified", help="统一存储目录")
    parser.add_argument("--keep-failed-samples", action="store_true", help="保存未通过评分的样本")
    args = parser.parse_args()

    tasks = build_tasks(args.stage)
    if args.task_jsonl:
        write_jsonl(tasks, args.task_jsonl)

    storage = TrainingStorage(base_dir=args.storage_dir)
    stats = execute_tasks(tasks, storage=storage, keep_failed_samples=args.keep_failed_samples)
    print(
        f"[SUMMARY] stage={args.stage} total={stats['total']} success={stats['success']} failed={stats['failed']}",
        flush=True,
    )
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
