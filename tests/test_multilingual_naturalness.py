from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.multilingual_naturalness import polish_generated_lines
from demo_app.rule_loader import clear_rule_cache, load_text_naturalness_rules


class MultilingualNaturalnessTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rule_cache()

    def test_rule_loader_accepts_naturalness_rules(self) -> None:
        payload = load_text_naturalness_rules()
        self.assertIn("Japanese", payload.get("languages", {}))
        self.assertIn("Spanish", payload.get("languages", {}))
        self.assertIn("Cantonese", payload.get("languages", {}))

    def test_polish_generated_lines_localizes_japanese_templates(self) -> None:
        lines = [
            ("Speaker 1", "您好，我叫Professional，是专业人士。今天我们来详细讨论。"),
            ("Speaker 2", "这个问题很重要，让我核实一下具体情况再回复您。"),
            ("Speaker 1", "The most important thing is: <<Core:membership growth>>"),
            ("Speaker 3", "这个问题是从什么时候开始的？"),
        ]
        polished, meta = polish_generated_lines(lines, "Japanese")
        self.assertEqual(polished[0][1], "こんにちは。今日は進め方を一緒に整理したいです。")
        self.assertEqual(polished[1][1], "重要な論点なので、前提条件を確認してから判断します。")
        self.assertTrue(polished[2][1].startswith("いちばん重要なのは、<<Core:"))
        self.assertEqual(polished[3][1], "この問題はいつ頃から表面化しましたか。")
        self.assertGreaterEqual(meta["rewrite_count"], 4)

    def test_polish_generated_lines_localizes_spanish_followups(self) -> None:
        lines = [
            ("Speaker 2", "我理解了，能否给我一些时间整理一下思路？"),
            ("Speaker 3", "从技术实现看，我会认真思考这个问题，准备好之后再向您汇报。需要考虑接口性能和降级策略。"),
            ("Speaker 1", "最重要的是： <<Core:membership growth>>"),
        ]
        polished, meta = polish_generated_lines(lines, "Spanish")
        self.assertEqual(polished[0][1], "Entiendo. ¿Puedo tomar un poco de tiempo para ordenar bien la idea?")
        self.assertEqual(
            polished[1][1],
            "Desde la implementación técnica, también hay que revisar el rendimiento de las interfaces y la estrategia de degradación.",
        )
        self.assertTrue(polished[2][1].startswith("Lo más importante es: <<Core:"))
        self.assertGreaterEqual(meta["rewrite_count"], 3)

    def test_polish_generated_lines_localizes_cantonese_templates(self) -> None:
        lines = [
            ("Speaker 1", "大家好，我是Professional，是专业人士。准备好了吗？"),
            ("Speaker 3", "我理解了，能否给我一些时间整理一下思路？"),
            ("Speaker 1", "The most important thing is: <<Core:會員增長>>"),
        ]
        polished, meta = polish_generated_lines(lines, "Cantonese")
        self.assertEqual(polished[0][1], "大家好，我哋先講清楚前提同做法。")
        self.assertEqual(polished[1][1], "明白，可唔可以畀我少少時間整理一下思路？")
        self.assertTrue(polished[2][1].startswith("最重要嘅係：<<Core:"))
        self.assertGreaterEqual(meta["rewrite_count"], 3)


if __name__ == "__main__":
    unittest.main()
