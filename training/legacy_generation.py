from __future__ import annotations

import re
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

# Languages whose bundle generation degrades to Chinese on large targets.
# Each individual call is capped at _CHUNK_SIZE; results are concatenated.
_CHUNK_LANGUAGES: frozenset[str] = frozenset({"日语", "韩语"})
_CHUNK_SIZE = 2500          # chars per independent call for chunk languages
_CHUNK_MAX_RETRIES = 2      # retries if a chunk fails language check


def _kana_ratio(text: str) -> float:
    kana = len(re.findall(r"[぀-ゟ゠-ヿ]", text))
    return kana / max(len(text), 1)


def _hangul_ratio(text: str) -> float:
    hangul = len(re.findall(r"[가-힯ᄀ-ᇿ]", text))
    return hangul / max(len(text), 1)


def _chunk_is_valid(lines: DialogueLines, language: str) -> bool:
    """Quick language sanity check on a single chunk."""
    if not lines:
        return False
    full = " ".join(t for _, t in lines)
    if language == "日语":
        return _kana_ratio(full) >= 0.08
    if language == "韩语":
        return _hangul_ratio(full) >= 0.05
    return True


def _build_profile(task: TrainingTask) -> dict:
    job = denormalize_task(task)
    return {
        "job_function": job["job_function"],
        "work_content": job["work_content"],
        "seniority": job["seniority"],
    }


def _generate_chunked(
    task: TrainingTask,
    seed_offset: int,
    bundle_server: Any,
    generate_fn: Any,
) -> Tuple[DialogueLines, Dict[str, Any]]:
    """
    Generate a large dialogue by making N independent small calls, each capped
    at _CHUNK_SIZE characters. Invalid chunks (wrong language) are retried up to
    _CHUNK_MAX_RETRIES times and then skipped.

    This avoids the cross-segment language drift that occurs when a single
    multi-segment loop accumulates Chinese-contaminated segments.
    """
    total_target = task.word_count
    n_chunks = max(1, -(-total_target // _CHUNK_SIZE))  # ceil division
    chunk_size = total_target // n_chunks

    profile = _build_profile(task)
    all_lines: DialogueLines = []
    total_chars = 0
    n_valid = 0
    last_rewrite_info: dict = {}

    for i in range(n_chunks):
        remaining = total_target - total_chars
        if remaining <= 0:
            break
        this_chunk_size = min(chunk_size, remaining)

        chunk_lines: DialogueLines = []
        for attempt in range(_CHUNK_MAX_RETRIES + 1):
            seg_lines, rewrite_info = generate_fn(
                bundle_server=bundle_server,
                profile=profile,
                scenario=task.scenario,
                core_content=task.core_content,
                people_count=task.people_count,
                total_target=this_chunk_size,
                language=task.language,
            )
            last_rewrite_info = rewrite_info
            if _chunk_is_valid(seg_lines, task.language):
                chunk_lines = seg_lines
                break
            # Invalid chunk — retry with slightly varied target to shake the bundle
            this_chunk_size = max(500, this_chunk_size - 100 * (attempt + 1))

        if chunk_lines:
            all_lines.extend(chunk_lines)
            total_chars += sum(len(t) for _, t in chunk_lines)
            n_valid += 1

    debug_info = {
        "rewrite_info": last_rewrite_info,
        "line_count": len(all_lines),
        "total_chars": total_chars,
        "seed": task.seed + seed_offset,
        "generator": "embedded_bundle_chunked_v1",
        "n_chunks": n_chunks,
        "n_valid_chunks": n_valid,
        "chunk_size": chunk_size,
    }
    return all_lines, debug_info


def generate_dialogue_for_task(task: TrainingTask, seed_offset: int = 0) -> Tuple[DialogueLines, Dict[str, Any]]:
    """
    Generate dialogue lines for a training task using the current embedded bundle server.

    For languages in _CHUNK_LANGUAGES (Japanese, Korean): splits the target into
    independent _CHUNK_SIZE calls to prevent cross-segment language drift.
    For all other languages: delegates to _generate_long_dialogue_lines directly,
    which already handles large targets via its own internal multi-segment loop.
    """
    from demo_app.embedded_server_main import (
        _generate_long_dialogue_lines,
        load_bundle_server,
    )

    bundle_server = load_bundle_server()

    if task.language in _CHUNK_LANGUAGES and task.word_count > _CHUNK_SIZE:
        return _generate_chunked(task, seed_offset, bundle_server, _generate_long_dialogue_lines)

    profile = _build_profile(task)
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
