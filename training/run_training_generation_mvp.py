"""统一训练生成入口，兼容旧 CLI。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from training.training_executor import execute_tasks
from training.training_job_adapters import normalize_jobs
from training.training_storage import TrainingStorage


def load_jobs(jobs_file: str) -> List[Dict]:
    jobs: List[Dict] = []
    with open(jobs_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                jobs.append(json.loads(line))
    return jobs


def _infer_stage(first_job: Dict) -> str:
    return "legacy_full" if "job_id" in first_job else "legacy_mvp"


def run_training_generation_mvp(jobs_file: str, output_dir: str, max_jobs: int = 999999):
    jobs = load_jobs(jobs_file)[:max_jobs]
    stage = _infer_stage(jobs[0]) if jobs else "legacy_mvp"
    tasks = normalize_jobs(jobs, stage=stage)
    storage = TrainingStorage(base_dir=output_dir)
    stats = execute_tasks(tasks, storage=storage, keep_failed_samples=False)

    print(f"[MVP批量生成] 总任务数: {stats['total']}")
    print(f"[MVP批量生成] 成功: {stats['success']} ({(stats['success'] / max(stats['total'], 1)) * 100:.1f}%)")
    print(f"[MVP批量生成] 失败: {stats['failed']}")
    print(f"[MVP批量生成] 输出目录: {output_dir}")
    print(f"[MVP批量生成] 失败记录: {storage.failed_path}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="批量生成训练语料（MVP版本）")
    parser.add_argument("--jobs", type=str, required=True, help="任务JSONL文件路径")
    parser.add_argument("--out_dir", type=str, required=True, help="输出目录")
    parser.add_argument("--max_jobs", type=int, default=999999, help="最大任务数")
    args = parser.parse_args()
    stats = run_training_generation_mvp(args.jobs, args.out_dir, args.max_jobs)
    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
