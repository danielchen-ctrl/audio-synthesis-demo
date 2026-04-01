from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.multilingual_naturalness import enforce_keywords_in_lines, polish_generated_lines, repair_dialogue_quality
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

    def test_repair_dialogue_quality_rebuilds_flat_secondary_lines(self) -> None:
        lines = [
            ("Speaker 1", "你好，我是王芳，我们先把系统稳定性这件事聊明白。"),
            ("Speaker 2", "这个我需要回去确认一下，明天给您答复可以吗？"),
            ("Speaker 3", "我会认真思考这个问题，准备好之后再向您汇报。"),
            ("Speaker 1", "现在大致有两种思路，我们可以一起权衡哪种更合适。"),
            ("Speaker 2", "我明白了，这个确实需要注意。"),
        ]
        repaired, meta = repair_dialogue_quality(
            lines,
            "Chinese",
            scenario="测试开发讨论上线前的系统稳定性和风险控制",
            core_content="接口超时、降级策略、回滚预案、灰度发布",
            profile={"work_content": "系统稳定性", "use_case": "评审会"},
            target_word_count=900,
            people_count=3,
            keywords=["接口超时", "降级策略"],
        )
        rendered = "\n".join(text for _, text in repaired)
        speaker_two_lines = [text for speaker, text in repaired if speaker == "Speaker 2"]
        speaker_three_lines = [text for speaker, text in repaired if speaker == "Speaker 3"]
        self.assertTrue(meta["repaired"])
        self.assertGreaterEqual(len(speaker_two_lines), 3)
        self.assertGreaterEqual(len(speaker_three_lines), 3)
        self.assertIn("接口超时", rendered)
        self.assertTrue(any("降级策略" in text for text in speaker_two_lines + speaker_three_lines))
        self.assertGreater(len(rendered.replace("\n", "")), 700)


if __name__ == "__main__":
    unittest.main()
