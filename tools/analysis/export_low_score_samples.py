#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_index(index_path: Path) -> List[dict]:
    if not index_path.exists():
        raise FileNotFoundError(f"index file not found: {index_path}")
    rows = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_score_file(path_str: str) -> Dict[str, Any]:
    path = Path(path_str)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_low_score_report(rows: List[dict], limit: int, stage: str = "") -> List[dict]:
    filtered = rows if not stage else [row for row in rows if row.get("stage") == stage]
    sorted_rows = sorted(filtered, key=lambda row: (float(row.get("score", 0.0)), row.get("task_id", "")))
    report = []
    for row in sorted_rows[:limit]:
        score_path = row.get("paths", {}).get("score_path", "")
        meta_path = row.get("paths", {}).get("meta_path", "")
        score_payload = load_score_file(score_path) if score_path else {}
        findings = score_payload.get("findings", [])
        report.append(
            {
                "task_id": row.get("task_id"),
                "stage": row.get("stage"),
                "job_function": row.get("job_function"),
                "language": row.get("language"),
                "scenario_id": row.get("scenario_id"),
                "passed": row.get("passed"),
                "score": row.get("score"),
                "meta_path": meta_path,
                "score_path": score_path,
                "finding_count": len(findings),
                "findings": findings,
            }
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="导出统一索引中的最低分样本及问题清单")
    parser.add_argument("--index", default="output/training/unified/_index.jsonl", help="统一索引文件路径")
    parser.add_argument("--limit", type=int, default=20, help="导出条数")
    parser.add_argument("--stage", default="", help="可选：只导出某个 stage")
    parser.add_argument("--out", default="output/training/unified/low_score_samples.json", help="输出 JSON 文件")
    args = parser.parse_args()

    rows = load_index(Path(args.index))
    report = build_low_score_report(rows, limit=args.limit, stage=args.stage)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "index": args.index,
        "limit": args.limit,
        "stage_filter": args.stage,
        "samples": report,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
