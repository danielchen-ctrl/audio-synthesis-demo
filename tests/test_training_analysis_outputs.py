# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tools.analysis.summarize_training_index import filter_rows, summarize_rows
from tools.analysis.export_low_score_samples import build_low_score_report


def _write_index(tmpdir: str) -> Path:
    index_path = Path(tmpdir) / "_index.jsonl"
    rows = [
        {
            "task_id": "a1",
            "stage": "legacy_mvp",
            "passed": True,
            "score": 88.5,
            "language": "中文",
            "job_function": "医疗健康",
            "scenario_id": "医疗健康-01",
            "paths": {},
        },
        {
            "task_id": "b2",
            "stage": "scene_regression",
            "passed": False,
            "score": 42.0,
            "language": "中文",
            "job_function": "企业管理",
            "scenario_id": "1",
            "paths": {},
        },
    ]
    with index_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return index_path


def test_summarize_rows_with_stage_filter():
    rows = [
        {"task_id": "a1", "stage": "legacy_mvp", "passed": True, "score": 88.5, "language": "中文", "job_function": "医疗健康"},
        {"task_id": "b2", "stage": "scene_regression", "passed": False, "score": 42.0, "language": "中文", "job_function": "企业管理"},
    ]
    filtered = filter_rows(rows, "scene_regression")
    assert len(filtered) == 1
    summary = summarize_rows(filtered)
    assert summary["total"] == 1
    assert summary["failed"] == 1
    assert summary["by_stage"]["scene_regression"]["total"] == 1


def test_build_low_score_report_orders_by_score():
    with tempfile.TemporaryDirectory(prefix="analysis_outputs_") as tmpdir:
        index_path = _write_index(tmpdir)
        rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        report = build_low_score_report(rows, limit=2, stage="")
        assert len(report) == 2
        assert report[0]["task_id"] == "b2"
        assert report[0]["score"] == 42.0
        assert report[1]["task_id"] == "a1"
