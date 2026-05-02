from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from training.training_job_adapters import denormalize_task
from training.training_types import ExecutionResult, TrainingTask


class TrainingStorage:
    def __init__(self, base_dir: str = "output/training/unified") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "_index.jsonl"
        self.failed_path = self.base_dir / "_failed.jsonl"

    def _safe(self, text: str) -> str:
        return text.replace("/", "_").replace("\\", "_")

    def sample_dir(self, task: TrainingTask, passed: bool = True) -> Path:
        profession = self._safe(task.profile.get("job_function", "未知职业"))
        language = self._safe(task.language)
        bucket = "passed" if passed else "failed_samples"
        return self.base_dir / bucket / task.stage / profession / language

    def sample_basename(self, task: TrainingTask) -> str:
        scenario_id = self._safe(task.meta.get("scenario_id", task.task_id))
        return f"{scenario_id}_{task.word_count}_{task.people_count}_{task.seed}"

    def save_result(self, result: ExecutionResult, keep_failed_sample: bool = False) -> Dict[str, str]:
        should_write_sample = result.score_report.passed or keep_failed_sample
        output_paths: Dict[str, str] = {}
        if should_write_sample:
            target_dir = self.sample_dir(result.task, passed=result.score_report.passed)
            target_dir.mkdir(parents=True, exist_ok=True)
            basename = self.sample_basename(result.task)
            txt_path = target_dir / f"{basename}.txt"
            meta_path = target_dir / f"{basename}.meta.json"
            score_path = target_dir / f"{basename}.score.json"

            with txt_path.open("w", encoding="utf-8") as f:
                for speaker, text in result.lines:
                    f.write(f"{speaker}: {text}\n")

            meta = self._build_meta(result)
            with meta_path.open("w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            with score_path.open("w", encoding="utf-8") as f:
                json.dump(result.score_report.to_dict(), f, ensure_ascii=False, indent=2)

            output_paths = {
                "txt_path": str(txt_path),
                "meta_path": str(meta_path),
                "score_path": str(score_path),
            }

        index_record = {
            "task_id": result.task.task_id,
            "stage": result.task.stage,
            "passed": result.score_report.passed,
            "score": result.score_report.score,
            "language": result.task.language,
            "job_function": result.task.profile.get("job_function"),
            "scenario_id": result.task.meta.get("scenario_id"),
            "paths": output_paths,
        }
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
        return output_paths

    def record_failure(self, task: TrainingTask, error: str) -> None:
        payload = denormalize_task(task)
        payload["task_id"] = task.task_id
        payload["stage"] = task.stage
        payload["error"] = error
        with self.failed_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _build_meta(self, result: ExecutionResult) -> Dict[str, Any]:
        task = result.task
        debug_info = dict(result.debug_info)
        speaker_distribution = result.score_report.metrics.get("speaker_distribution", {})
        return {
            "task_id": task.task_id,
            "stage": task.stage,
            "job_function": task.profile.get("job_function", "未知职业"),
            "language": task.language,
            "scenario": task.scenario,
            "core_content": task.core_content,
            "people_count": task.people_count,
            "word_count": task.word_count,
            "seed": task.seed,
            "effective_params": {
                "scenario_head": task.scenario[:60],
                "core_head": task.core_content[:60],
                "people_count": task.people_count,
                "word_count": task.word_count,
                "language": task.language,
            },
            "debug_info": debug_info,
            "stats": {
                "line_count": len(result.lines),
                "total_chars": result.score_report.metrics.get("total_chars", 0),
                "speaker_distribution": speaker_distribution,
            },
            "quality": result.score_report.to_dict(),
        }
