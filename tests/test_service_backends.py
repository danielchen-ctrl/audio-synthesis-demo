from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import tempfile
import unittest
import warnings
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.app_state import AppState, DialogueRecord
from demo_app.audio_backends import BundleAudioGenerator, SourceAudioGenerator, build_audio_backend
from demo_app.backend_common import GeneratedDialogue
from demo_app.legacy_runtime_adapters import LegacyAudioAdapter, LegacyTextAdapter
from demo_app.legacy_runtime_gateway import LegacyRuntimeGateway
from demo_app.text_service import generate_text
from demo_app.text_backends import BundleTextGenerator, SourceTextGenerator, build_text_backend
from demo_app.audio_service import generate_audio


class FakeTextBackend:
    def __init__(self):
        self.saved_manifest = None

    def validate_payload(self, payload):
        return dict(payload)

    def get_generation_config(self):
        return {"prefer_v2_for_scenes": ["review"]}

    def classify_scene_type(self, scenario, profile):
        return "review"

    def generate_v2(self, profile, scenario, core, people, target_len, language):
        return GeneratedDialogue(
            lines=[("Speaker 1", "criteria defined"), ("Speaker 2", "thresholds finalized")],
            debug_info={"from_v2": True, "is_from_v2": True},
        )

    def generate_fallback(self, profile, scenario, core, people, target_len, language):
        raise AssertionError("fallback should not run in this test")

    def save_manifest(self, save_dir, dialogue_id, timestamp, basename, text_path, language, profile):
        self.saved_manifest = {
            "save_dir": str(save_dir),
            "dialogue_id": dialogue_id,
            "timestamp": timestamp,
            "basename": basename,
            "text_path": text_path,
            "language": language,
        }


class FakeAudioBackend:
    def get_autogate_param(self, path, default=None):
        if path == "tts.enable_ssml":
            return False
        return default

    async def run_attempt(
        self,
        lines,
        output_wav_path,
        language,
        pause_ms,
        dialogue_id,
        timestamp,
        voice_rotation,
        disable_ssml,
        skip_translation,
        pause_profile,
    ):
        output_wav_path.write_bytes(b"RIFFfakeWAVE")
        return (
            True,
            "",
            {1: "en-US-GuyNeural"},
            [{"speaker": "Speaker 1", "text": "hello world", "voice": "en-US-GuyNeural", "line_index": 0, "duration_ms": 500}],
            "",
            "",
            "",
        )


class FallbackTrackingTextBackend:
    def __init__(self):
        self.generate_v2_calls = 0
        self.generate_fallback_calls = 0

    def validate_payload(self, payload):
        return dict(payload)

    def get_generation_config(self):
        return {}

    def classify_scene_type(self, scenario, profile):
        return ""

    def generate_v2(self, profile, scenario, core, people, target_len, language):
        self.generate_v2_calls += 1
        return GeneratedDialogue(
            lines=[("Speaker 1", "bundle fallback line")],
            debug_info={"from_v2": True, "is_from_v2": True, "generator_version": "dialogue_generator_v2_bundle"},
        )

    def generate_fallback(self, profile, scenario, core, people, target_len, language):
        self.generate_fallback_calls += 1
        return GeneratedDialogue(
            lines=[("Speaker 1", "bundle fallback generator line")],
            debug_info={"from_v2": False, "is_from_v2": False, "generator_version": "bundle_fallback_text_generator"},
        )

    def save_manifest(self, save_dir, dialogue_id, timestamp, basename, text_path, language, profile):
        return None


class ServiceBackendTests(unittest.TestCase):
    def test_backend_factory_defaults_to_source_text_and_bundle_audio(self) -> None:
        text_backend = build_text_backend("source_first")
        audio_backend = build_audio_backend("source_policy")
        self.assertIsInstance(text_backend, SourceTextGenerator)
        self.assertIsInstance(audio_backend, SourceAudioGenerator)

    def test_backend_factory_can_force_bundle_text(self) -> None:
        text_backend = build_text_backend("bundle")
        self.assertIsInstance(text_backend, BundleTextGenerator)

    def test_backend_factory_can_force_bundle_audio(self) -> None:
        audio_backend = build_audio_backend("bundle")
        self.assertIsInstance(audio_backend, BundleAudioGenerator)

    def test_bundle_generators_delegate_runtime_access_to_legacy_gateway(self) -> None:
        text_backend = BundleTextGenerator(runtime_module=SimpleNamespace())
        audio_backend = BundleAudioGenerator(runtime_module=SimpleNamespace())
        self.assertIsInstance(text_backend.gateway, LegacyRuntimeGateway)
        self.assertIsInstance(audio_backend.gateway, LegacyRuntimeGateway)

    def test_legacy_runtime_adapters_are_deprecated_wrappers(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            text_adapter = LegacyTextAdapter(runtime_module=SimpleNamespace())
            audio_adapter = LegacyAudioAdapter(runtime_module=SimpleNamespace())
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))
        self.assertIsInstance(text_adapter.gateway, LegacyRuntimeGateway)
        self.assertIsInstance(audio_adapter.gateway, LegacyRuntimeGateway)

    def test_source_text_generator_respects_disabled_bundle_fallback_policy(self) -> None:
        backend = FallbackTrackingTextBackend()
        generator = SourceTextGenerator(fallback=backend)

        @contextlib.contextmanager
        def broken_source_modules():
            raise RuntimeError("source backend failed")
            yield

        generator._source_modules = broken_source_modules
        with patch("demo_app.text_backends.allow_bundle_fallback", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "bundle fallback is disabled"):
                generator.generate_v2({}, "review", "core", 2, 200, "English")
        self.assertEqual(backend.generate_v2_calls, 0)

    def test_source_audio_generator_prefers_source_autogate_config(self) -> None:
        runtime_module = SimpleNamespace(get_autogate_param=lambda path, default=None: 999)
        backend = SourceAudioGenerator(runtime_module=runtime_module)
        backend.source_autogate_config = {"tts": {"enable_ssml": True, "ssml": {"comma_break_ms": 123}}}
        self.assertEqual(backend.get_autogate_param("tts.ssml.comma_break_ms", 0), 123)
        self.assertEqual(backend.get_autogate_param("tts.unknown_value", 77), 999)

    def test_source_audio_generator_prefers_source_engine(self) -> None:
        runtime_module = SimpleNamespace(get_autogate_param=lambda path, default=None: default)
        backend = SourceAudioGenerator(runtime_module=runtime_module)

        async def fake_engine(**kwargs):
            return (True, "", {"Speaker 1": "en-US-GuyNeural"}, [{"speaker": "Speaker 1", "text": "hello", "voice": "en-US-GuyNeural", "line_index": 0, "duration_ms": 500}], "tts.txt", "align.json", "")

        with patch("demo_app.audio_backends.synthesize_dialogue_audio", new=fake_engine):
            result = asyncio.run(
                backend.run_attempt(
                    lines=[("Speaker 1", "hello")],
                    output_wav_path=Path(tempfile.gettempdir()) / "source_audio_generator.wav",
                    language="English",
                    pause_ms=200,
                    dialogue_id="dlg",
                    timestamp="20260307_120000",
                    voice_rotation=0,
                    disable_ssml=False,
                    skip_translation=False,
                    pause_profile={"comma_break_ms": 120, "sentence_break_ms": 350, "speaker_change_extra_ms": 180},
                )
            )
        self.assertTrue(result[0])
        self.assertEqual(backend.last_engine_name, "source_audio_engine")

    def test_source_audio_generator_falls_back_to_bundle_when_engine_raises(self) -> None:
        runtime_module = SimpleNamespace(get_autogate_param=lambda path, default=None: default)
        backend = SourceAudioGenerator(runtime_module=runtime_module)

        async def broken_engine(**kwargs):
            raise RuntimeError("source audio engine failed")

        async def fake_bundle_run_attempt(self, **kwargs):
            return (True, "", {"Speaker 1": "en-US-GuyNeural"}, [{"speaker": "Speaker 1", "text": "hello", "voice": "en-US-GuyNeural", "line_index": 0, "duration_ms": 500}], "tts.txt", "align.json", "")

        with patch("demo_app.audio_backends.synthesize_dialogue_audio", new=broken_engine), patch.object(BundleAudioGenerator, "run_attempt", new=fake_bundle_run_attempt):
            result = asyncio.run(
                backend.run_attempt(
                    lines=[("Speaker 1", "hello")],
                    output_wav_path=Path(tempfile.gettempdir()) / "source_audio_generator_fallback.wav",
                    language="English",
                    pause_ms=200,
                    dialogue_id="dlg",
                    timestamp="20260307_120000",
                    voice_rotation=0,
                    disable_ssml=False,
                    skip_translation=False,
                    pause_profile={"comma_break_ms": 120, "sentence_break_ms": 350, "speaker_change_extra_ms": 180},
                )
            )
        self.assertTrue(result[0])
        self.assertEqual(backend.last_engine_name, "bundle_runtime_fallback")

    def test_source_audio_generator_respects_disabled_bundle_fallback_policy(self) -> None:
        runtime_module = SimpleNamespace(get_autogate_param=lambda path, default=None: default)
        backend = SourceAudioGenerator(runtime_module=runtime_module)

        async def broken_engine(**kwargs):
            raise RuntimeError("source audio engine failed")

        with patch("demo_app.audio_backends.synthesize_dialogue_audio", new=broken_engine), patch("demo_app.audio_backends.allow_bundle_fallback", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "source audio engine failed"):
                asyncio.run(
                    backend.run_attempt(
                        lines=[("Speaker 1", "hello")],
                        output_wav_path=Path(tempfile.gettempdir()) / "source_audio_generator_disabled_fallback.wav",
                        language="English",
                        pause_ms=200,
                        dialogue_id="dlg",
                        timestamp="20260307_120000",
                        voice_rotation=0,
                        disable_ssml=False,
                        skip_translation=False,
                        pause_profile={"comma_break_ms": 120, "sentence_break_ms": 350, "speaker_change_extra_ms": 180},
                    )
                )

    def test_generate_text_accepts_backend_and_persists_state(self) -> None:
        state = AppState()
        backend = FakeTextBackend()
        payload = {
            "title": "backend_review",
            "profile": {"job_function": "Backend", "seniority": "Senior"},
            "scenario": "review",
            "core_content": "criteria defined; thresholds finalized",
            "people_count": 2,
            "word_count": 200,
            "audio_language": "English",
        }
        quality_result = {
            "passed": True,
            "score": 0,
            "role_mapping": {"Speaker 1": "PM", "Speaker 2": "Backend"},
            "report": {"overall": {"passed": True, "total_errors": 0, "total_warnings": 0}},
            "report_markdown": "",
            "summary": {"passed": True, "total_errors": 0, "total_warnings": 0, "blocking_issues": 0},
        }
        with tempfile.TemporaryDirectory() as tempdir, patch("demo_app.text_service.resolve_project_path", return_value=Path(tempdir)), patch("demo_app.text_service._run_quality_gate", return_value=quality_result):
            response = generate_text(payload, state, generator=backend)
        self.assertTrue(response["ok"])
        self.assertTrue(response["debug"]["from_v2"])
        self.assertEqual(response["debug"]["text_backend"], "FakeTextBackend")
        self.assertEqual(state.latest().dialogue_id, response["dialogue_id"])
        self.assertIsNotNone(backend.saved_manifest)

    def test_generate_audio_accepts_backend_and_writes_alignment_files(self) -> None:
        state = AppState()
        with tempfile.TemporaryDirectory() as tempdir, patch("demo_app.audio_service._convert_wav_to_mp3", return_value=""):
            folder = Path(tempdir)
            record = DialogueRecord(
                dialogue_id="dlg-1",
                timestamp="20260307_120000",
                folder_path=str(folder),
                basename="backend_review_English_20260307_120000",
                language="English",
                profile={},
                lines=[("Speaker 1", "hello world")],
                dialogue_text="Speaker 1: hello world",
                text_path=str(folder / "dialogue.txt"),
            )
            state.remember(record)
            response = asyncio.run(generate_audio({"dialogue_id": "dlg-1", "audio_language": "English"}, state, generator=FakeAudioBackend()))
            self.assertTrue(response["ok"])
            self.assertEqual(response["format"], "wav")
            self.assertEqual(response["audio_backend"], "FakeAudioBackend")
            self.assertTrue(Path(response["segments_json_path"]).exists())
            self.assertTrue(Path(response["transcript_vtt_path"]).exists())

    def test_source_text_generator_prefers_source_modules(self) -> None:
        backend = FallbackTrackingTextBackend()
        generator = SourceTextGenerator(fallback=backend)

        @contextlib.contextmanager
        def fake_source_modules():
            module = SimpleNamespace(
                _generate_intelligent_dialogue=lambda **kwargs: (
                    [("Speaker 1", "source line")],
                    {"from_v2": True, "is_from_v2": True},
                )
            )
            yield module, SimpleNamespace()

        generator._source_modules = fake_source_modules
        result = generator.generate_v2({}, "review", "core", 2, 200, "English")
        self.assertEqual(result.lines[0][1], "source line")
        self.assertTrue(result.debug_info["source_generator"])
        self.assertFalse(result.debug_info["source_v2_fallback"])
        self.assertEqual(backend.generate_v2_calls, 0)

    def test_source_text_generator_falls_back_to_bundle_when_source_fails(self) -> None:
        backend = FallbackTrackingTextBackend()
        generator = SourceTextGenerator(fallback=backend)

        @contextlib.contextmanager
        def broken_source_modules():
            raise RuntimeError("source backend failed")
            yield

        generator._source_modules = broken_source_modules
        result = generator.generate_v2({}, "review", "core", 2, 200, "English")
        self.assertEqual(result.lines[0][1], "bundle fallback line")
        self.assertFalse(result.debug_info["source_generator"])
        self.assertTrue(result.debug_info["source_v2_fallback"])
        self.assertIn("source backend failed", result.debug_info["source_v2_error"])
        self.assertEqual(backend.generate_v2_calls, 1)

    def test_source_text_generator_uses_source_validation_policy(self) -> None:
        generator = SourceTextGenerator(fallback=FallbackTrackingTextBackend())
        normalized = generator.validate_payload(
            {
                "profile": {"job_function": "Backend", "seniority": "Senior"},
                "scenario": "review",
                "word_count": 120,
                "people_count": "3",
                "audio_language": "English",
            }
        )
        self.assertEqual(normalized["title"], "dialogue")
        self.assertEqual(normalized["word_count"], 500)
        self.assertEqual(normalized["people_count"], 3)
        self.assertEqual(normalized["audio_language"], "English")

    def test_source_text_generator_uses_source_scene_classifier(self) -> None:
        generator = SourceTextGenerator(fallback=FallbackTrackingTextBackend())
        self.assertEqual(generator.classify_scene_type("architecture review", {}), "review")
        self.assertEqual(generator.classify_scene_type("go/no-go decision", {}), "decision")
        self.assertEqual(generator.classify_scene_type("weekly sync meeting", {}), "meeting")

    def test_source_text_generator_writes_manifest_without_bundle(self) -> None:
        generator = SourceTextGenerator(fallback=FallbackTrackingTextBackend())
        with tempfile.TemporaryDirectory() as tempdir:
            folder = Path(tempdir)
            generator.save_manifest(
                save_dir=folder,
                dialogue_id="dlg-source",
                timestamp="20260307_150000",
                basename="dialogue_English_20260307_150000",
                text_path=str(folder / "dialogue.txt"),
                language="English",
                profile={"job_function": "Backend", "seniority": "Senior"},
            )
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["dialogue_id"], "dlg-source")
        self.assertEqual(manifest["audio_language"], "English")
        self.assertEqual(manifest["profile"]["job_function"], "Backend")

    def test_source_text_generator_prefers_source_fallback_generator(self) -> None:
        backend = FallbackTrackingTextBackend()
        generator = SourceTextGenerator(fallback=backend)
        result = generator.generate_fallback(
            {"job_function": "Backend", "seniority": "Senior"},
            "consultation",
            "Core Facts:\n- criteria defined\n- owner assigned\nAction Items:\n- finalize monitoring\n- publish rollback checklist",
            3,
            500,
            "English",
        )
        self.assertTrue(result.debug_info["source_fallback_generator"])
        self.assertFalse(result.debug_info["source_fallback_bundle_fallback"])
        self.assertEqual(backend.generate_fallback_calls, 0)
        self.assertGreaterEqual(len(result.lines), 6)

    def test_source_text_generator_falls_back_to_bundle_fallback_generator_when_source_fails(self) -> None:
        backend = FallbackTrackingTextBackend()
        generator = SourceTextGenerator(fallback=backend)
        with patch("demo_app.text_backends.generate_fallback_dialogue_source", side_effect=RuntimeError("source fallback failed")):
            result = generator.generate_fallback(
                {"job_function": "Backend", "seniority": "Senior"},
                "consultation",
                "criteria defined; owner assigned",
                2,
                500,
                "English",
            )
        self.assertFalse(result.debug_info["source_fallback_generator"])
        self.assertTrue(result.debug_info["source_fallback_bundle_fallback"])
        self.assertIn("source fallback failed", result.debug_info["source_fallback_error"])
        self.assertEqual(backend.generate_fallback_calls, 1)

    def test_runtime_patches_is_deprecated_legacy_wrapper(self) -> None:
        sys.modules.pop("demo_app.runtime_patches", None)
        sys.modules.pop("demo_app.runtime_patches_legacy", None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            import demo_app.runtime_patches as runtime_patches

        self.assertTrue(any(item.category is DeprecationWarning for item in caught))
        self.assertNotIn("demo_app.runtime_patches_legacy", sys.modules)
        self.assertTrue(hasattr(runtime_patches, "apply_runtime_patches"))
        self.assertIn("demo_app.runtime_patches_legacy", sys.modules)

    def test_runtime_patches_restricts_export_surface(self) -> None:
        sys.modules.pop("demo_app.runtime_patches", None)
        import demo_app.runtime_patches as runtime_patches

        self.assertEqual(
            sorted(runtime_patches.__all__),
            ["apply_runtime_patches", "load_server_module", "mount_project_bundle"],
        )
        with self.assertRaises(AttributeError):
            getattr(runtime_patches, "_pick_variant")


if __name__ == "__main__":
    unittest.main()
