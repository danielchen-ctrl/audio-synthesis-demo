from __future__ import annotations

from typing import Any, Dict, Tuple

from training.training_job_adapters import denormalize_task
from training.training_types import DialogueLines, TrainingTask


def generate_dialogue_for_task(task: TrainingTask, seed_offset: int = 0) -> Tuple[DialogueLines, Dict[str, Any]]:
    job = denormalize_task(task)
    profile_dict = {
        "job_function": job["job_function"],
        "work_content": job["work_content"],
        "seniority": job["seniority"],
    }

    from server import classify_scene_type, _generate_cast, _generate_structured_dialogue

    scene_type = classify_scene_type(task.scenario, profile_dict)
    cast_info = _generate_cast(profile_dict, task.scenario, task.people_count, task.language)
    lines = _generate_structured_dialogue(
        cast_info=cast_info,
        profile=profile_dict,
        scenario=task.scenario,
        core=task.core_content,
        target_len=task.word_count,
        language=task.language,
        total_people=task.people_count,
    )
    debug_info = {
        "scene_type": scene_type,
        "cast_count": len(cast_info),
        "line_count": len(lines),
        "total_chars": sum(len(text) for _, text in lines),
        "from_v2": False,
        "seed": task.seed + seed_offset,
    }
    return lines, debug_info
