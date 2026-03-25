from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import enforce_pre_release_ci_gate as enforce_script
import run_pre_release_ci_gate as gate_script


class PreReleaseGateTests(unittest.TestCase):
    def test_markdown_report_includes_multilingual_check(self):
        payload = {
            "generated_at": "2026-03-21T12:00:00",
            "status": "ok",
            "checks": {
                "required_paths": {"status": "ok"},
                "yaml_parse": {"status": "ok"},
                "python_compile": {"status": "ok"},
                "repo_daily_check": {"status": "ok"},
                "multilingual_quality_check": {
                    "status": "ok",
                    "payload": {
                        "summary": {
                            "error_count": 0,
                            "warning_count": 1,
                            "scripted_language_count": 7,
                            "source_text_language_count": 7,
                            "source_audio_language_count": 7,
                        }
                    },
                },
                "embedded_demo_smoke": {"status": "ok", "base_url": "http://127.0.0.1:8899/", "dialogue_id": "demo", "log_path": "runtime/temp/demo.log"},
            },
            "blocking_failures": [],
            "warnings": [],
        }
        report = gate_script._markdown_report(payload)
        self.assertIn("Multilingual quality check", report)
        self.assertIn("Multilingual Quality Summary", report)
        self.assertIn("Source-only text languages", report)

    def test_enforce_rejects_multilingual_failure(self):
        payload = {
            "generated_at": "2026-03-21T12:00:00",
            "status": "ok",
            "checks": {
                "required_paths": {"status": "ok"},
                "yaml_parse": {"status": "ok"},
                "python_compile": {"status": "ok"},
                "repo_daily_check": {"status": "ok"},
                "multilingual_quality_check": {"status": "error"},
                "embedded_demo_smoke": {"status": "ok"},
            },
        }
        with tempfile.TemporaryDirectory() as tempdir:
            report = Path(tempdir) / "latest.json"
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(AssertionError):
                enforce_script.main(["--report", str(report), "--max-age-hours", "24"])


if __name__ == "__main__":
    unittest.main()
