import tempfile
import unittest
from pathlib import Path

from training.build_training_jobs_full import build_training_jobs_full
from training.translation_helpers import chinese_ratio


class TranslationFallbacksTest(unittest.TestCase):
    def test_full_job_builder_avoids_chinese_heavy_fallback_for_english_and_japanese(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "jobs.jsonl"
            build_training_jobs_full(str(output_path), use_translate=False)

            english_lines = []
            japanese_lines = []
            for line in output_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                if '"language": "英语"' in line and len(english_lines) < 3:
                    english_lines.append(line)
                if '"language": "日语"' in line and len(japanese_lines) < 3:
                    japanese_lines.append(line)
                if len(english_lines) >= 3 and len(japanese_lines) >= 3:
                    break

            self.assertEqual(len(english_lines), 3)
            self.assertEqual(len(japanese_lines), 3)

            for raw in english_lines + japanese_lines:
                self.assertNotIn("[EN]", raw)
                self.assertNotIn("[JA]", raw)
                self.assertLess(chinese_ratio(raw), 0.25)


if __name__ == "__main__":
    unittest.main()
