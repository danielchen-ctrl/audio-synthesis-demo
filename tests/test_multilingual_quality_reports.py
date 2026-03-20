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

import run_multilingual_quality_checks as report_script


class MultilingualQualityReportTests(unittest.TestCase):
    def test_script_level_failures_are_reported(self):
        result = {
            "script": "run_multilingual_text_service_smoke.py",
            "exit_code": 1,
            "parse_error": "stdout is empty",
            "status": "error",
            "payload": None,
            "stdout": "",
            "stderr": "boom",
        }
        failures = report_script._analyze_scripted_result(result)
        self.assertEqual(len(failures), 2)
        messages = [item["message"] for item in failures]
        self.assertTrue(any("exited with code 1" in message for message in messages))
        self.assertTrue(any("没有返回稳定 JSON" in message for message in messages))

    def test_source_only_failures_generate_actionable_summary(self):
        result = {
            "script": "run_multilingual_pre_release_source_only_check.py",
            "exit_code": 0,
            "parse_error": "",
            "status": "ok",
            "stdout": "{}",
            "stderr": "",
            "payload": {
                "results": [
                    {
                        "language": "Japanese",
                        "scenario": "meeting",
                        "text_ok": True,
                        "quality_passed": False,
                        "text_backend": "BundleTextGenerator",
                        "source_v2_fallback": False,
                        "source_fallback_bundle_fallback": True,
                    }
                ],
                "audio_results": [
                    {
                        "language": "Japanese",
                        "audio_ok": False,
                        "audio_backend": "BundleAudioGenerator",
                        "audio_engine": "bundle_audio_engine",
                        "segments_exists": False,
                        "vtt_exists": False,
                        "expected_audio_backend": "SourceAudioGenerator",
                        "expected_audio_engine": "source_audio_engine",
                    }
                ],
            },
        }
        failures = report_script._analyze_source_only_result(result)
        self.assertGreaterEqual(len(failures), 5)
        self.assertTrue(any(item["component"] == "quality_gate" for item in failures))
        self.assertTrue(any(item["component"] == "legacy_text_fallback" for item in failures))
        self.assertTrue(any(item["component"] == "audio_backend" for item in failures))
        self.assertTrue(any(item["component"] == "segments" for item in failures))

    def test_write_reports_persists_latest_and_timestamped_files(self):
        scripted = {
            "script": "a.py",
            "status": "ok",
            "exit_code": 0,
            "stdout": "{}",
            "stderr": "",
            "parse_error": "",
            "payload": {"results": []},
        }
        source_only = {
            "script": "b.py",
            "status": "ok",
            "exit_code": 0,
            "stdout": "{}",
            "stderr": "",
            "parse_error": "",
            "payload": {"results": [], "audio_results": []},
        }
        failures = []
        payload = {
            "entrypoint": "run_multilingual_quality_checks",
            "report_schema_version": "1.0",
            "generated_at": "2026-03-21T12:00:00",
            "checks": {
                "scripted_multilingual_text_service_smoke": scripted,
                "multilingual_pre_release_source_only": source_only,
            },
            "failure_summary": failures,
            "suggested_actions": [],
        }
        payload["summary"] = report_script._build_summary(scripted, source_only, failures)
        payload["status"] = payload["summary"]["latest_status"]

        with tempfile.TemporaryDirectory() as tmp:
            report_paths = report_script._write_reports(payload, Path(tmp))
            latest_json = Path(report_paths["latest_json"])
            latest_md = Path(report_paths["latest_markdown"])
            self.assertTrue(latest_json.exists())
            self.assertTrue(latest_md.exists())
            report_json = json.loads(latest_json.read_text(encoding="utf-8"))
            self.assertEqual(report_json["status"], "ok")
            report_md = latest_md.read_text(encoding="utf-8")
            self.assertIn("Failure Summary", report_md)
            self.assertIn("No failures detected.", report_md)


if __name__ == "__main__":
    unittest.main()
