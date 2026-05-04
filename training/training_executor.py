from __future__ import annotations

import concurrent.futures
from typing import Callable, Dict, Iterable, Optional

from training.dialogue_validators import validate_with_quality_gate
from training.legacy_generation import generate_dialogue_for_task
from training.quality_scoring import score_dialogue
from training.training_storage import TrainingStorage
from training.training_types import ExecutionResult, TrainingTask


Generator = Callable[[TrainingTask, int], tuple]

# Maximum seconds a single generator() call may run before being abandoned.
# 10-speaker tasks can spin inside the bundle for 30+ min; cap at 5 min.
_GENERATOR_TIMEOUT_SECONDS = 300


def _call_with_timeout(fn, *args, timeout: int = _GENERATOR_TIMEOUT_SECONDS):
    """Run fn(*args) in a thread; raise TimeoutError if it exceeds `timeout` s."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        return future.result(timeout=timeout)


def execute_tasks(
    tasks: Iterable[TrainingTask],
    storage: Optional[TrainingStorage] = None,
    keep_failed_samples: bool = False,
    max_retries: int = 2,
    generator: Optional[Generator] = None,
) -> Dict[str, int]:
    storage = storage or TrainingStorage()
    generator = generator or generate_dialogue_for_task
    stats = {"total": 0, "success": 0, "failed": 0}

    for task in tasks:
        stats["total"] += 1
        success = False
        last_error = ""
        for retry in range(max_retries + 1):
            try:
                lines, debug_info = _call_with_timeout(generator, task, retry)
                validation = validate_with_quality_gate(task, lines)
                score_report = score_dialogue(task, lines, validator_errors=validation["errors"])
                result = ExecutionResult(
                    task=task,
                    lines=lines,
                    debug_info=debug_info,
                    score_report=score_report,
                )
                result.output_paths = storage.save_result(result, keep_failed_sample=keep_failed_samples)
                if not score_report.passed:
                    last_error = validation["summary"]
                    if retry < max_retries:
                        continue
                    storage.record_failure(task, last_error)
                    stats["failed"] += 1
                    break
                stats["success"] += 1
                success = True
                break
            except Exception as exc:
                last_error = str(exc)
                if retry >= max_retries:
                    storage.record_failure(task, last_error)
                    stats["failed"] += 1
                    break
        if not success and not last_error:
            stats["failed"] += 1
    return stats
