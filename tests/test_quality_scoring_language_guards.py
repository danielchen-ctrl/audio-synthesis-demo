import unittest

from training.quality_scoring import score_dialogue
from training.training_types import TrainingTask


def make_task(language: str, translate_fallback: bool = True) -> TrainingTask:
    return TrainingTask(
        task_id=f"task-{language}",
        stage="cross_combo",
        profile={"job_function": "AI and Technology"},
        scenario="placeholder scenario",
        core_content="placeholder core",
        language=language,
        people_count=2,
        word_count=120,
        seed=1,
        meta={"scenario_id": "demo", "translate_fallback": translate_fallback},
    )


class QualityScoringLanguageGuardsTest(unittest.TestCase):
    def test_japanese_dialogue_with_kana_is_not_misclassified_as_high_chinese_ratio(self) -> None:
        report = score_dialogue(
            make_task("日语"),
            [
                ("Speaker 1", "今日は会議の進め方を確認します。"),
                ("Speaker 2", "リスクと次の対応も整理しましょう。"),
                ("Speaker 1", "担当者と期限をここで決めます。"),
                ("Speaker 2", "最後に要点を日本語でまとめます。"),
            ],
        )
        self.assertNotIn("high_chinese_ratio", {item.code for item in report.findings})

    def test_english_dialogue_with_chinese_content_still_flags_high_chinese_ratio(self) -> None:
        report = score_dialogue(
            make_task("英语", translate_fallback=False),
            [
                ("Speaker 1", "我们先确认本周目标。"),
                ("Speaker 2", "再讨论风险和下一步安排。"),
                ("Speaker 1", "最后同步负责人和时间点。"),
            ],
        )
        self.assertIn("high_chinese_ratio", {item.code for item in report.findings})


if __name__ == "__main__":
    unittest.main()
