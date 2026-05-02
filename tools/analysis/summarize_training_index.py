#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def load_index(index_path: Path) -> List[dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"index file not found: {index_path}")
    rows = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def summarize_rows(rows: List[dict]) -> Dict[str, object]:
    by_stage: Dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0, "avg_score": 0.0})
    by_language: Dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    by_job_function: Dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    total_score = 0.0

    for row in rows:
        passed = bool(row.get("passed"))
        score = float(row.get("score", 0.0))
        stage = row.get("stage", "unknown")
        language = row.get("language", "unknown")
        job_function = row.get("job_function", "unknown")

        bucket = by_stage[stage]
        bucket["total"] += 1
        bucket["passed"] += 1 if passed else 0
        bucket["failed"] += 0 if passed else 1
        bucket["avg_score"] += score

        lang_bucket = by_language[language]
        lang_bucket["total"] += 1
        lang_bucket["passed"] += 1 if passed else 0
        lang_bucket["failed"] += 0 if passed else 1

        job_bucket = by_job_function[job_function]
        job_bucket["total"] += 1
        job_bucket["passed"] += 1 if passed else 0
        job_bucket["failed"] += 0 if passed else 1

        total_score += score

    for stage, bucket in by_stage.items():
        bucket["avg_score"] = round(bucket["avg_score"] / max(bucket["total"], 1), 2)

    return {
        "total": len(rows),
        "passed": sum(1 for row in rows if row.get("passed")),
        "failed": sum(1 for row in rows if not row.get("passed")),
        "avg_score": round(total_score / max(len(rows), 1), 2),
        "by_stage": dict(sorted(by_stage.items())),
        "by_language": dict(sorted(by_language.items())),
        "by_job_function": dict(sorted(by_job_function.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="汇总统一训练索引 _index.jsonl")
    parser.add_argument("--index", default="output/training/unified/_index.jsonl", help="统一索引文件路径")
    parser.add_argument("--out", default="", help="可选：把汇总 JSON 写到指定文件")
    args = parser.parse_args()

    index_path = Path(args.index)
    rows = load_index(index_path)
    summary = summarize_rows(rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
