import json
import tempfile
import unittest
from pathlib import Path

from training.training_executor import execute_tasks
from training.training_storage import TrainingStorage
from training.training_types import TrainingTask


def build_task() -> TrainingTask:
    return TrainingTask(
        task_id="task-low-score",
        stage="foundation_templates",
        profile={"job_function": "售前顾问"},
        scenario="为客户演示音频合成方案",
        core_content="介绍多人对话生成能力",
        language="中文",
        people_count=2,
        word_count=120,
        seed=7,
        meta={"scenario_id": "demo_case"},
    )


def failing_generator(task: TrainingTask, retry: int):
    lines = [
        ("Speaker 1", "先放一个 [[[CORE 占位符，后面再补。"),
        ("Speaker 2", "好的。"),
        ("Speaker 1", "这版先演示流程。"),
    ]
    return lines, {"retry": retry, "generator": "test-double"}


class TrainingExportRegressionTest(unittest.TestCase):
    def test_failed_sample_is_exported_with_findings_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TrainingStorage(base_dir=tmpdir)

            stats = execute_tasks(
                [build_task()],
                storage=storage,
                keep_failed_samples=True,
                max_retries=0,
                generator=failing_generator,
            )

            self.assertEqual(stats, {"total": 1, "success": 0, "failed": 1})

            failed_dir = (
                Path(tmpdir) / "failed_samples" / "foundation_templates" / "售前顾问" / "中文"
            )
            score_files = list(failed_dir.glob("*.score.json"))
            meta_files = list(failed_dir.glob("*.meta.json"))
            text_files = list(failed_dir.glob("*.txt"))

            self.assertEqual(len(score_files), 1)
            self.assertEqual(len(meta_files), 1)
            self.assertEqual(len(text_files), 1)

            score_payload = json.loads(score_files[0].read_text(encoding="utf-8"))
            self.assertFalse(score_payload["passed"])
            self.assertLess(score_payload["score"], 60)
            self.assertTrue(score_payload["findings"])

            finding_codes = {item["code"] for item in score_payload["findings"]}
            self.assertIn("placeholder_leak", finding_codes)
            self.assertIn("missing_core_marker", finding_codes)

            meta_payload = json.loads(meta_files[0].read_text(encoding="utf-8"))
            self.assertIn("quality", meta_payload)
            self.assertEqual(meta_payload["quality"]["findings"], score_payload["findings"])

    def test_failed_sample_is_not_exported_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TrainingStorage(base_dir=tmpdir)

            stats = execute_tasks(
                [build_task()],
                storage=storage,
                keep_failed_samples=False,
                max_retries=0,
                generator=failing_generator,
            )

            self.assertEqual(stats, {"total": 1, "success": 0, "failed": 1})
            self.assertFalse(list(Path(tmpdir).glob("**/*.txt")))
            self.assertFalse(list(Path(tmpdir).glob("**/*.meta.json")))
            self.assertFalse(list(Path(tmpdir).glob("**/*.score.json")))

            index_lines = (Path(tmpdir) / "_index.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(index_lines), 1)
            index_payload = json.loads(index_lines[0])
            self.assertFalse(index_payload["passed"])
            self.assertEqual(index_payload["paths"], {})


if __name__ == "__main__":
    unittest.main()
