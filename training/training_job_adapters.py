from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List

from training.training_types import TrainingTask


def _task_id(parts: Iterable[str]) -> str:
    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def normalize_job(job: Dict[str, Any], stage: str = "legacy_mvp") -> TrainingTask:
    if "job_function" in job:
        profession = job["job_function"]
        profile = {
            "job_function": profession,
            "work_content": job["work_content"],
            "seniority": job["seniority"],
        }
        meta = dict(job.get("meta", {}))
        scenario_id = meta.get("scenario_id", profession)
        task_id = _task_id(
            [
                stage,
                profession,
                scenario_id,
                job["language"],
                str(job["word_count"]),
                str(job["people_count"]),
                str(job["seed"]),
            ]
        )
        return TrainingTask(
            task_id=task_id,
            stage=stage,
            profile=profile,
            scenario=job["scenario"],
            core_content=job["core_content"],
            language=job["language"],
            people_count=job["people_count"],
            word_count=job["word_count"],
            seed=job["seed"],
            meta=meta,
            source_format="mvp",
        )

    profession = job.get("profession", job.get("profile", {}).get("job_function", "未知职业"))
    profile = dict(job.get("profile", {}))
    scenario_id = job.get("scenario_id", profession)
    task_id = str(job.get("job_id") or _task_id([stage, profession, scenario_id, job["language"], str(job["seed"])]))
    meta = {
        "scenario_id": scenario_id,
        "translate_fallback": job.get("translate_fallback", False),
    }
    return TrainingTask(
        task_id=task_id,
        stage=stage,
        profile=profile,
        scenario=job["scenario"],
        core_content=job["core_content"],
        language=job["language"],
        people_count=job["people_count"],
        word_count=job["word_count"],
        seed=job["seed"],
        meta=meta,
        source_format="full",
    )


def denormalize_task(task: TrainingTask) -> Dict[str, Any]:
    job_function = task.profile.get("job_function", "未知职业")
    work_content = task.profile.get("work_content", "综合管理")
    seniority = task.profile.get("seniority", "经理")
    return {
        "job_function": job_function,
        "work_content": work_content,
        "seniority": seniority,
        "scenario": task.scenario,
        "core_content": task.core_content,
        "language": task.language,
        "people_count": task.people_count,
        "word_count": task.word_count,
        "seed": task.seed,
        "meta": dict(task.meta),
    }


def normalize_jobs(jobs: List[Dict[str, Any]], stage: str = "legacy_mvp") -> List[TrainingTask]:
    return [normalize_job(job, stage=stage) for job in jobs]
