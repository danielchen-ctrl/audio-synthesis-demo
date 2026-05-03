from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Tuple

# Ensure src/ is on sys.path so demo_app can be imported directly
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from training.training_job_adapters import denormalize_task
from training.training_types import DialogueLines, TrainingTask


def generate_dialogue_for_task(task: TrainingTask, seed_offset: int = 0) -> Tuple[DialogueLines, Dict[str, Any]]:
    """
    Generate dialogue lines for a training task using the current embedded bundle server.

    Replaces the old approach that called classify_scene_type / _generate_cast /
    _generate_structured_dialogue from server.py (functions that no longer exist in
    the main-branch server.py). Now delegates directly to load_bundle_server() +
    _generate_long_dialogue_lines() from embedded_server_main.
    """
    from demo_app.embedded_server_main import (
        _generate_long_dialogue_lines,
        load_bundle_server,
    )

    job = denormalize_task(task)
    profile = {
        "job_function": job["job_function"],
        "work_content": job["work_content"],
        "seniority": job["seniority"],
    }

    bundle_server = load_bundle_server()
    lines, rewrite_info = _generate_long_dialogue_lines(
        bundle_server=bundle_server,
        profile=profile,
        scenario=task.scenario,
        core_content=task.core_content,
        people_count=task.people_count,
        total_target=task.word_count,
        language=task.language,
    )

    debug_info = {
        "rewrite_info": rewrite_info,
        "line_count": len(lines),
        "total_chars": sum(len(text) for _, text in lines),
        "seed": task.seed + seed_offset,
        "generator": "embedded_bundle_v1",
    }
    return lines, debug_info
