from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.app_state import AppState
from demo_app.backend_common import GeneratedDialogue
from demo_app.text_service import canonical_language, generate_text, normalize_generation_payload


class FakeEnglishCleanupBackend:
    def validate_payload(self, payload):
        return dict(payload)

    def get_generation_config(self):
        return {"prefer_v2_for_scenes": ["meeting"]}

    def classify_scene_type(self, scenario, profile):
        return "meeting"

    def generate_v2(self, profile, scenario, core, people, target_len, language):
        return GeneratedDialogue(
            lines=[
                ("Speaker 1", "Hello, I'm Zhang Hao, project lead. Let's discuss your situation regarding meeting."),
                ("Speaker 2", "Yes, Zhang Hao. I mainly want to understand requirements clarification."),
                ("Speaker 1", "Could you provide more details?"),
                ("Speaker 2", "The situation is quite specific."),
                ("Speaker 1", "What's the specific amount or number?"),
                ("Speaker 3", "To add, regarding procedures, we need X days. This is confirmed."),
            ],
            debug_info={"from_v2": True, "is_from_v2": True, "generator_version": "fake_english_cleanup_backend"},
        )

    def generate_fallback(self, profile, scenario, core, people, target_len, language):
        raise AssertionError("fallback should not be used in this test")

    def save_manifest(self, save_dir, dialogue_id, timestamp, basename, text_path, language, profile):
        return None


class FakeCantoneseConsultationV2Backend:
    def validate_payload(self, payload):
        return dict(payload)

    def get_generation_config(self):
        return {"prefer_v2_for_scenes": ["meeting", "review", "decision"]}

    def classify_scene_type(self, scenario, profile):
        return "consultation"

    def generate_v2(self, profile, scenario, core, people, target_len, language):
        return GeneratedDialogue(
            lines=[
                ("Speaker 1", "Hello, I'm 王睿, 项目负责人. Let's discuss your situation regarding consultation."),
                ("Speaker 2", "Yes, 王睿. I mainly want to understand 需求澄清."),
                ("Speaker 1", "Could you provide more details?"),
            ],
            debug_info={"from_v2": True, "is_from_v2": True, "generator_version": "fake_cantonese_consultation_v2"},
        )

    def generate_fallback(self, profile, scenario, core, people, target_len, language):
        raise AssertionError("fallback should not be used in this cantonese v2 test")

    def save_manifest(self, save_dir, dialogue_id, timestamp, basename, text_path, language, profile):
        return None


class TextServiceRefactorTests(unittest.TestCase):
    def test_canonical_language_normalizes_known_values(self) -> None:
        self.assertEqual(canonical_language("Chinese"), "Chinese")
        self.assertEqual(canonical_language("中文"), "Chinese")
        self.assertEqual(canonical_language("English"), "English")
        self.assertEqual(canonical_language("en-US"), "English")
        self.assertEqual(canonical_language("en"), "English")
        self.assertEqual(canonical_language("Japanese"), "Japanese")
        self.assertEqual(canonical_language("日本語"), "Japanese")
        self.assertEqual(canonical_language("Korean"), "Korean")
        self.assertEqual(canonical_language("ko-KR"), "Korean")
        self.assertEqual(canonical_language("한국어"), "Korean")
        self.assertEqual(canonical_language("French"), "French")
        self.assertEqual(canonical_language("fr-FR"), "French")
        self.assertEqual(canonical_language("German"), "German")
        self.assertEqual(canonical_language("Deutsch"), "German")
        self.assertEqual(canonical_language("Spanish"), "Spanish")
        self.assertEqual(canonical_language("Español"), "Spanish")
        self.assertEqual(canonical_language("Portuguese"), "Portuguese")
        self.assertEqual(canonical_language("Português"), "Portuguese")
        self.assertEqual(canonical_language("Cantonese"), "Cantonese")
        self.assertEqual(canonical_language("粤语"), "Cantonese")

    def test_normalize_generation_payload_prefers_non_chinese_explicit_language(self) -> None:
        payload = {"language": "zh", "audio_language": "English"}
        normalized = normalize_generation_payload(payload)
        self.assertEqual(normalized["language"], "English")
        self.assertEqual(normalized["audio_language"], "English")

    def test_normalize_generation_payload_backfills_missing_language(self) -> None:
        payload = {"audio_language": "English"}
        normalized = normalize_generation_payload(payload)
        self.assertEqual(normalized["language"], "English")
        self.assertEqual(normalized["audio_language"], "English")

    def test_normalize_generation_payload_prefers_other_supported_non_chinese_languages(self) -> None:
        payload = {"language": "zh", "audio_language": "French"}
        normalized = normalize_generation_payload(payload)
        self.assertEqual(normalized["language"], "French")
        self.assertEqual(normalized["audio_language"], "French")

    def test_normalize_generation_payload_prefers_new_supported_non_chinese_languages(self) -> None:
        payload = {"language": "zh", "audio_language": "Spanish"}
        normalized = normalize_generation_payload(payload)
        self.assertEqual(normalized["language"], "Spanish")
        self.assertEqual(normalized["audio_language"], "Spanish")
        payload = {"language": "zh", "audio_language": "Portuguese"}
        normalized = normalize_generation_payload(payload)
        self.assertEqual(normalized["language"], "Portuguese")
        self.assertEqual(normalized["audio_language"], "Portuguese")
        payload = {"language": "zh", "audio_language": "粤语"}
        normalized = normalize_generation_payload(payload)
        self.assertEqual(normalized["language"], "Cantonese")
        self.assertEqual(normalized["audio_language"], "Cantonese")

    def test_generate_text_cleans_english_placeholder_and_filler_phrases(self) -> None:
        payload = {
            "profile": {"job_function": "backend", "seniority": "senior"},
            "scenario": "meeting",
            "language": "English",
            "audio_language": "English",
            "people_count": 3,
            "word_count": 700,
            "core_content": "requirements clarification; rollback owner assigned; acceptance gate explicit",
        }
        response = generate_text(payload, AppState(), generator=FakeEnglishCleanupBackend())
        self.assertTrue(response["ok"])
        self.assertTrue(response["debug"]["quality_gate"]["passed"])
        joined = " ".join(item["text"] for item in response["lines"])
        for banned in [
            "Let's discuss your situation regarding meeting",
            "Could you provide more details",
            "The situation is quite specific",
            "What's the specific amount or number",
            "This is confirmed",
            "Already prepared",
        ]:
            self.assertNotIn(banned, joined)
        self.assertIn("I mainly want to clarify the requirements and scope.", joined)
        self.assertIn("We still need a concrete timeline and named owner.", joined)

    def test_generate_text_prefers_v2_for_cantonese_consultation(self) -> None:
        payload = {
            "profile": {"job_function": "backend", "seniority": "senior"},
            "scenario": "consultation",
            "language": "Cantonese",
            "audio_language": "Cantonese",
            "people_count": 3,
            "word_count": 700,
            "core_content": "customer asks for trade-offs; owner assigned; monitoring thresholds finalized; rollback checklist published",
        }
        response = generate_text(payload, AppState(), generator=FakeCantoneseConsultationV2Backend())
        self.assertTrue(response["ok"])
        self.assertTrue(response["debug"]["from_v2"])
        joined = " ".join(item["text"] for item in response["lines"])
        self.assertIn("我哋先討論一下今次 consultation。", joined)
        self.assertIn("我主要想確認需求釐清。", joined)
        self.assertNotIn("Let's discuss your situation regarding consultation", joined)
        self.assertNotIn("Could you provide more details", joined)


if __name__ == "__main__":
    unittest.main()
