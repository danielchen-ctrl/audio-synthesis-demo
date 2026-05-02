# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from training.run_scene_dialogue_regression import build_scene_summary, build_scene_task
from training.training_storage import TrainingStorage
from training.training_types import ExecutionResult
from training.quality_scoring import score_dialogue


def _make_result(storage: TrainingStorage, scenario_num: str = "1") -> ExecutionResult:
    task = build_scene_task(
        scenario_num=scenario_num,
        scenario_setup="示例场景设置",
        core_content="示例核心内容",
        people_count=3,
        target_len=1000,
        language="中文",
    )
    lines = [
        ("Tim(CEO)", "我先说明今天的目标和关键背景。<<核心:示例核心内容>>"),
        ("张秘书(CEO办公室首席助理)", "我会记录行动项并同步节奏。"),
        ("李总监(增长部负责人)", "我补充增长侧的判断和资源安排。"),
    ] * 4
    report = score_dialogue(task, lines, validator_errors=[])
    result = ExecutionResult(
        task=task,
        lines=lines,
        debug_info={"scene_type": "scene_1", "line_count": len(lines), "total_chars": sum(len(t) for _, t in lines)},
        score_report=report,
    )
    result.output_paths = storage.save_result(result, keep_failed_sample=True)
    return result


def test_scene_summary_builder_counts():
    results = [
        {"scenario_num": "1", "status": "success", "validation_passed": True, "score": 88.0},
        {"scenario_num": "2", "status": "failed", "validation_passed": False, "score": 42.0},
    ]
    summary = build_scene_summary(results)
    assert summary["total_scenarios"] == 2
    assert summary["success_count"] == 1
    assert summary["validation_passed_count"] == 1
    assert len(summary["results"]) == 2


def test_scene_storage_outputs_include_score_and_meta():
    with tempfile.TemporaryDirectory(prefix="scene_regression_test_") as tmpdir:
        storage = TrainingStorage(base_dir=tmpdir)
        result = _make_result(storage)

        txt_path = Path(result.output_paths["txt_path"])
        meta_path = Path(result.output_paths["meta_path"])
        score_path = Path(result.output_paths["score_path"])
        index_path = Path(tmpdir) / "_index.jsonl"

        assert txt_path.exists()
        assert meta_path.exists()
        assert score_path.exists()
        assert index_path.exists()

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        score = json.loads(score_path.read_text(encoding="utf-8"))
        index_rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        assert meta["stage"] == "scene_regression"
        assert "quality" in meta
        assert "passed" in score and "score" in score and "metrics" in score
        assert len(index_rows) == 1
        assert index_rows[0]["stage"] == "scene_regression"
        assert index_rows[0]["paths"]["score_path"].endswith(".score.json")
