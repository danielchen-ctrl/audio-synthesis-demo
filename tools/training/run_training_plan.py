#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_training_plan.py
====================
按训练阶段或 batch 执行统一训练计划。

支持两种调用方式：

方式 A（旧接口，保持兼容）：
  python tools/training/run_training_plan.py \
    --stage foundation_templates \
    --storage-dir output/training/unified \
    --keep-failed-samples

方式 B（v2 新接口，匹配训练方案执行文档）：
  python tools/training/run_training_plan.py \
    --batch b0_smoke \
    --jobs training/data/training_jobs_b0_smoke.jsonl \
    --out_dir output/training_v2 \
    --mode internal \
    --resume \
    --max_retries 2 \
    --keep-failed-samples
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.task_matrix_builder import STAGE_SPECS, build_tasks, write_jsonl
from training.training_executor import execute_tasks
from training.training_job_adapters import normalize_job
from training.training_storage import TrainingStorage
from training.training_types import TrainingTask


# ─────────────────────────────────────────────────────
# 辅助：从 JSONL 加载任务（v2 batch 接口用）
# ─────────────────────────────────────────────────────

def _load_tasks_from_jsonl(path: str, stage: str) -> list[TrainingTask]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"任务文件不存在: {path}")
    tasks = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            job = json.loads(line)
            tasks.append(normalize_job(job, stage=stage))
    return tasks


def _load_completed_task_ids(storage_dir: str) -> set[str]:
    """从 _index.jsonl 读取已完成的 task_id，用于 --resume 断点续跑。"""
    index_path = Path(storage_dir) / "_index.jsonl"
    if not index_path.exists():
        return set()
    done: set[str] = set()
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                tid = record.get("task_id")
                if tid and record.get("passed"):
                    done.add(tid)
            except Exception:
                pass
    return done


# ─────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="执行训练计划（支持旧 --stage 和新 --batch 接口）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── 方式 A：旧接口 ──
    parser.add_argument(
        "--stage",
        choices=list(STAGE_SPECS),
        default="",
        help="旧接口：训练阶段名称",
    )
    parser.add_argument(
        "--task-jsonl",
        type=str,
        default="",
        help="旧接口：把生成的任务写到此 JSONL 路径",
    )
    parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="旧接口：统一存储目录（默认 output/training/unified）",
    )

    # ── 方式 B：v2 新接口 ──
    parser.add_argument(
        "--batch",
        type=str,
        default="",
        help="v2接口：batch 名称（b0_smoke / b1_foundation / ...）",
    )
    parser.add_argument(
        "--jobs",
        type=str,
        default="",
        help="v2接口：任务 JSONL 文件路径",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="output/training_v2",
        help="v2接口：输出根目录（默认 output/training_v2）",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="internal",
        choices=["internal"],
        help="v2接口：生成模式，当前只支持 internal（使用内置 bundle server）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="v2接口：断点续跑，跳过 _index.jsonl 中已通过的 task_id",
    )

    # ── 公共参数 ──
    parser.add_argument(
        "--keep-failed-samples",
        action="store_true",
        help="保存未通过质量评分的样本（写入 failed_samples/）",
    )
    parser.add_argument(
        "--max_retries",
        type=int,
        default=2,
        help="每个任务最多重试次数（默认 2）",
    )

    args = parser.parse_args()

    # ── 路由：旧接口 vs 新接口 ──
    use_v2 = bool(args.batch)
    use_v1 = bool(args.stage)

    if use_v2 and use_v1:
        parser.error("--batch 和 --stage 不能同时使用")
    if not use_v2 and not use_v1:
        parser.error("必须指定 --batch 或 --stage 之一")

    # ── v2 路径 ──
    if use_v2:
        batch = args.batch

        # 确定存储目录：out_dir / batch名
        storage_dir = str(Path(args.out_dir) / batch)

        # 确定任务文件
        jobs_path = args.jobs
        if not jobs_path:
            jobs_path = str(ROOT / "training" / "data" / f"training_jobs_{batch}.jsonl")

        if not Path(jobs_path).exists():
            print(
                f"[错误] 任务文件不存在: {jobs_path}\n"
                f"  请先运行: python tools/training/build_training_plan_jobs.py --batch {batch}",
                file=sys.stderr,
            )
            sys.exit(1)

        tasks = _load_tasks_from_jsonl(jobs_path, stage=batch)
        print(f"[run_training_plan] batch={batch}  任务总数={len(tasks)}")

        # 断点续跑
        if args.resume:
            done_ids = _load_completed_task_ids(storage_dir)
            if done_ids:
                before = len(tasks)
                tasks = [t for t in tasks if t.task_id not in done_ids]
                print(f"  --resume: 跳过已完成 {before - len(tasks)} 个，剩余 {len(tasks)} 个")

        storage = TrainingStorage(base_dir=storage_dir)
        stats = execute_tasks(
            tasks,
            storage=storage,
            keep_failed_samples=args.keep_failed_samples,
            max_retries=args.max_retries,
        )
        print(
            f"[SUMMARY] batch={batch} "
            f"total={stats['total']} success={stats['success']} failed={stats['failed']}",
            flush=True,
        )
        if stats["failed"] > 0:
            sys.exit(1)
        return

    # ── v1 路径（保持原有逻辑）──
    stage = args.stage
    storage_dir = args.storage_dir or "output/training/unified"
    tasks = build_tasks(stage)
    if args.task_jsonl:
        write_jsonl(tasks, args.task_jsonl)
    storage = TrainingStorage(base_dir=storage_dir)
    stats = execute_tasks(
        tasks,
        storage=storage,
        keep_failed_samples=args.keep_failed_samples,
        max_retries=args.max_retries,
    )
    print(
        f"[SUMMARY] stage={stage} "
        f"total={stats['total']} success={stats['success']} failed={stats['failed']}",
        flush=True,
    )
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
