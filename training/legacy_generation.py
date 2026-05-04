from __future__ import annotations

import dataclasses
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
# Bundle generates ~300 chars of Japanese per call regardless of target size.
# Smaller chunk size means more calls and more accumulated content.
_CHUNK_SIZE = 500           # chars per independent call for chunk languages
_MAX_CHUNKS = 40            # safety cap: avoids excessive calls on 30k+ targets
_CHUNK_MAX_RETRIES = 2      # retries if a chunk fails language check
# Bundle RoleKPI enforcement fails for these languages beyond this speaker count
_PEOPLE_COUNT_CAP: dict[str, int] = {"日语": 8, "韩语": 8}

# Matches the "Scenario: <description>" artifact that the bundle embeds into
# English/non-Chinese dialogue lines (e.g. "around Scenario: A professional
# business discussion conducted in En."). Greedy match to end of sentence.
_SCENARIO_ARTIFACT_RE = re.compile(r"\s*Scenario:\s+[A-Za-z][^.!?\n<]*[.!?]?")
# Matches <<核心:…>> / <<Core:…>> / <<コア:…>> etc. template markers
_MARKER_RE = re.compile(r"<<[^>]+>>")
# Trailing dangling prepositions left after stripping the Scenario phrase
_TRAILING_PREP_RE = re.compile(
    r"\s+(around|about|on|for|in|of|with|to|and|or|the|a|an)\s*$",
    re.IGNORECASE,
)


def _clean_lines(lines: DialogueLines, language: str) -> DialogueLines:
    """Strip known bundle render artifacts from generated lines.

    - Removes <<marker>> templates from all non-Chinese languages.
    - Removes "Scenario: <description>" substrings from non-CJK languages
      (English, French, German, Spanish, etc.) where the bundle leaks the
      scenario prompt text directly into the dialogue content.
    """
    if language in ("中文", "粤语"):
        return lines

    cleaned: DialogueLines = []
    for speaker, text in lines:
        # Strip <<…>> markers
        text = _MARKER_RE.sub("", text).strip()
        # Strip "Scenario: description" artifact (non-CJK only; Japanese/Korean
        # do not exhibit this pattern and stripping could corrupt valid text)
        if language not in ("日语", "韩语"):
            text = _SCENARIO_ARTIFACT_RE.sub("", text).strip()
            text = _TRAILING_PREP_RE.sub("", text).strip()
        if text:
            cleaned.append((speaker, text))
    return cleaned


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
    """Generate a large dialogue by making N independent small calls.

    Each call is capped at _CHUNK_SIZE characters (_MAX_CHUNKS total cap).
    Invalid chunks (wrong language) are retried up to _CHUNK_MAX_RETRIES times
    and then skipped. Duplicate lines across chunks are deduplicated.

    Background: the bundle generates ~300 chars of Japanese per call regardless
    of the target. Using _CHUNK_SIZE=500 instead of 2500 produces ~5× more calls
    for the same target, accumulating enough content to pass the 40% word-count
    gate.
    """
    total_target = task.word_count
    n_chunks = min(_MAX_CHUNKS, max(1, -(-total_target // _CHUNK_SIZE)))  # ceil, capped
    chunk_size = max(_CHUNK_SIZE, total_target // n_chunks)

    profile = _build_profile(task)
    all_lines: DialogueLines = []
    seen_texts: set[str] = set()
    total_chars = 0
    n_valid = 0
    last_rewrite_info: dict = {}

    for i in range(n_chunks):
        remaining = total_target - total_chars
        if remaining <= 0:
            break
        this_chunk_size = min(chunk_size, max(_CHUNK_SIZE, remaining))

        chunk_lines: DialogueLines = []
        for attempt in range(_CHUNK_MAX_RETRIES + 1):
            try:
                seg_lines, rewrite_info = generate_fn(
                    bundle_server=bundle_server,
                    profile=profile,
                    scenario=task.scenario,
                    core_content=task.core_content,
                    people_count=task.people_count,
                    total_target=this_chunk_size,
                    language=task.language,
                )
            except (RuntimeError, Exception):
                # Bundle internal errors (e.g. RoleKPIHardFail) — treat as invalid chunk
                this_chunk_size = max(300, this_chunk_size - 100 * (attempt + 1))
                continue
            last_rewrite_info = rewrite_info
            if _chunk_is_valid(seg_lines, task.language):
                chunk_lines = seg_lines
                break
            this_chunk_size = max(300, this_chunk_size - 100 * (attempt + 1))

        if chunk_lines:
            for spk, txt in chunk_lines:
                if txt not in seen_texts:
                    seen_texts.add(txt)
                    all_lines.append((spk, txt))
                    total_chars += len(txt)
            n_valid += 1

    debug_info = {
        "rewrite_info": last_rewrite_info,
        "line_count": len(all_lines),
        "total_chars": total_chars,
        "seed": task.seed + seed_offset,
        "generator": "embedded_bundle_chunked_v2",
        "n_chunks": n_chunks,
        "n_valid_chunks": n_valid,
        "chunk_size": chunk_size,
    }
    return all_lines, debug_info


def generate_dialogue_for_task(task: TrainingTask, seed_offset: int = 0) -> Tuple[DialogueLines, Dict[str, Any]]:
    """Generate dialogue lines for a training task using the embedded bundle server.

    For languages in _CHUNK_LANGUAGES (Japanese, Korean): splits the target into
    independent _CHUNK_SIZE calls to accumulate enough content, and caps
    people_count at _PEOPLE_COUNT_CAP to avoid bundle RoleKPI failures.
    For all other languages: delegates to _generate_long_dialogue_lines directly.

    Post-generation: applies _clean_lines() to strip bundle render artifacts
    (Scenario: placeholder, <<marker>> templates) before returning.
    """
    from demo_app.embedded_server_main import (
        _generate_long_dialogue_lines,
        load_bundle_server,
    )

    # Cap speaker count for languages where bundle RoleKPI enforcement breaks down
    if task.language in _PEOPLE_COUNT_CAP:
        cap = _PEOPLE_COUNT_CAP[task.language]
        if task.people_count > cap:
            task = dataclasses.replace(task, people_count=cap)

    bundle_server = load_bundle_server()

    if task.language in _CHUNK_LANGUAGES and task.word_count > _CHUNK_SIZE:
        lines, debug_info = _generate_chunked(task, seed_offset, bundle_server, _generate_long_dialogue_lines)
    else:
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

    lines = _clean_lines(lines, task.language)
    return lines, debug_info
