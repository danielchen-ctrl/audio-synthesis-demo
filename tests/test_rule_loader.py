from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.rule_loader import clear_rule_cache, load_text_postprocess_rules, load_text_quality_rules


class RuleLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_rule_cache()

    def tearDown(self) -> None:
        clear_rule_cache()

    def test_loaders_accept_current_rule_files(self) -> None:
        self.assertIn("English", load_text_postprocess_rules().get("multilingual_fact_summary_prefix", {}))
        self.assertIn("QA", load_text_quality_rules().get("persona_rules", {}))

    def test_loader_rejects_invalid_rule_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config_dir = Path(tempdir)
            (config_dir / "text_postprocess_rules.yaml").write_text(
                yaml.safe_dump({"english_cjk_term_rewrites": []}, allow_unicode=True),
                encoding="utf-8",
            )
            with patch("demo_app.rule_loader.CONFIG_DIR", config_dir):
                clear_rule_cache()
                with self.assertRaises(ValueError):
                    load_text_postprocess_rules()


if __name__ == "__main__":
    unittest.main()
