from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.multilingual_naturalness import enforce_keywords_in_lines, polish_generated_lines
from demo_app.rule_loader import clear_rule_cache, load_text_naturalness_rules


class MultilingualNaturalnessTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rule_cache()

    def test_rule_loader_accepts_naturalness_rules(self) -> None:
        payload = load_text_naturalness_rules()
        self.assertIn("Japanese", payload.get("languages", {}))
        self.assertIn("Spanish", payload.get("languages", {}))
        self.assertIn("Cantonese", payload.get("languages", {}))

    def test_polish_generated_lines_keeps_non_chinese_rule_path_available(self) -> None:
        lines = [("Speaker 1", "The most important thing is: <<Core:membership growth>>")]
        polished, meta = polish_generated_lines(lines, "English")
        self.assertEqual(polished, lines)
        self.assertEqual(meta["rewrite_count"], 0)

    def test_polish_generated_lines_rewrites_chinese_placeholders_and_noise(self) -> None:
        lines = [
            ("Speaker 1", "您好，我是Professional，是专业人士。我们开始吧。"),
            ("Speaker 2", "您好，我是Counterpart。乐意参加讨论。"),
            ("Speaker 1", "The most important thing is: <<Core:chronic disease management + follow-up system upgrade>>"),
            ("Speaker 2", "Risk Alert: 质量目标 requires attention, 完成率 currently at 82%, needs monitoring."),
        ]
        polished, meta = polish_generated_lines(
            lines,
            "Chinese",
            scenario="病人和医生讨论慢病复诊安排",
            core_content="慢病管理和复诊安排",
            profile={"work_content": "慢病复诊", "use_case": "问诊"},
        )
        rendered = "\n".join(text for _, text in polished)
        self.assertGreaterEqual(meta["rewrite_count"], 3)
        self.assertNotIn("Professional", rendered)
        self.assertNotIn("Counterpart", rendered)
        self.assertNotIn("<<Core:", rendered)
        self.assertNotIn("Risk Alert", rendered)
        self.assertRegex(polished[0][1], r"^你好，我是[\u4e00-\u9fff]{2,4}")
        self.assertRegex(polished[1][1], r"^你好，我是[\u4e00-\u9fff]{2,4}")
        self.assertTrue(any("慢病管理和复诊安排" in text or "病人和医生讨论慢病复诊安排" in text for _, text in polished))

    def test_polish_generated_lines_rewrites_boilerplate_sentences(self) -> None:
        lines = [
            ("Speaker 1", "基于刚才的讨论，我建议我们有几个选择："),
            ("Speaker 1", "方案1: 方案一是快速推进，两周内完成，但可能需要您这边配合加班。"),
            ("Speaker 1", "方案2: 方案二是稳步推进，一个月完成，时间更充裕，质量更有保障。"),
        ]
        polished, _ = polish_generated_lines(lines, "Chinese", scenario="季度项目讨论", core_content="", profile={})
        self.assertEqual(polished[0][1], "现在大致有两种思路，我们可以一起权衡哪种更合适。")
        self.assertEqual(polished[1][1], "一种做法是先从最关键的部分开始，边推进边看效果。")
        self.assertEqual(polished[2][1], "另一种做法是先把方案准备充分，再整体往下推。")

    def test_enforce_keywords_in_lines_weaves_missing_keywords_naturally_for_chinese(self) -> None:
        lines = [
            ("Speaker 1", "你好，我们先把现在的情况梳理一下。"),
            ("Speaker 2", "好，我最想知道接下来应该怎么推进。"),
        ]
        updated, missing = enforce_keywords_in_lines(
            lines,
            ["慢病管理", "复诊率"],
            "Chinese",
            scenario="医院慢病随访讨论",
            core_content="慢病管理策略",
            profile={"work_content": "慢病随访"},
        )
        self.assertEqual(missing, ["慢病管理", "复诊率"])
        self.assertGreater(len(updated), len(lines))
        rendered = "\n".join(text for _, text in updated)
        self.assertIn("慢病管理", rendered)
        self.assertIn("复诊率", rendered)
        self.assertNotIn("明确提到这些关键词", rendered)


if __name__ == "__main__":
    unittest.main()
