from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List

from training.build_training_jobs_full import build_training_jobs_full
from training.build_training_jobs_mvp import build_training_jobs_mvp
from training.training_job_adapters import normalize_jobs
from training.training_types import TrainingTask


STAGE_SPECS: Dict[str, Dict[str, object]] = {
    "foundation_templates": {"source": "mvp", "limit": 48},
    "manual_aligned": {"source": "mvp", "limit": 96},
    "cross_combo": {"source": "full", "limit": 180, "use_translate": False},
    "long_dialogue_special": {"source": "full", "limit": 120, "min_word_count": 3000, "use_translate": False},
    "stress_large_speakers": {"source": "full", "limit": 90, "min_people_count": 3, "use_translate": False},
    "runtime_few_shot": {"source": "full", "limit": 120, "languages": {"中文", "英语", "日语"}, "use_translate": False},
}


def _read_jsonl(path: str) -> List[dict]:
    jobs: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                jobs.append(json.loads(line))
    return jobs


def _build_source_jobs(spec: Dict[str, object]) -> List[dict]:
    with tempfile.TemporaryDirectory(prefix="training_plan_") as tmpdir:
        jobs_path = str(Path(tmpdir) / "jobs.jsonl")
        if spec["source"] == "mvp":
            build_training_jobs_mvp(jobs_path, base_seed=20260126)
        else:
            build_training_jobs_full(
                jobs_path,
                base_seed=20260126,
                use_translate=bool(spec.get("use_translate", False)),
            )
        return _read_jsonl(jobs_path)


def build_tasks(stage: str) -> List[TrainingTask]:
    if stage not in STAGE_SPECS:
        raise ValueError(f"未知训练阶段: {stage}")
    spec = STAGE_SPECS[stage]
    jobs = _build_source_jobs(spec)
    if spec.get("min_word_count") is not None:
        jobs = [job for job in jobs if job["word_count"] >= spec["min_word_count"]]
    if spec.get("min_people_count") is not None:
        jobs = [job for job in jobs if job["people_count"] >= spec["min_people_count"]]
    if spec.get("languages"):
        languages = spec["languages"]
        jobs = [job for job in jobs if job["language"] in languages]
    limit = int(spec.get("limit", len(jobs)))
    tasks = normalize_jobs(jobs[:limit], stage=stage)
    return tasks


def write_jsonl(tasks: Iterable[TrainingTask], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for task in tasks:
            record = {
                "task_id": task.task_id,
                "stage": task.stage,
                "profile": task.profile,
                "scenario": task.scenario,
                "core_content": task.core_content,
                "language": task.language,
                "people_count": task.people_count,
                "word_count": task.word_count,
                "seed": task.seed,
                "meta": task.meta,
                "source_format": task.source_format,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
