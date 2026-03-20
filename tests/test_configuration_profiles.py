from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app import configuration


class ConfigurationProfileTests(unittest.TestCase):
    def test_pre_release_profile_overlays_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            config_dir = Path(tempdir)
            (config_dir / "app.yaml").write_text("", encoding="utf-8")
            (config_dir / "paths.yaml").write_text("", encoding="utf-8")
            (config_dir / "logging.yaml").write_text("", encoding="utf-8")
            (config_dir / "runtime.yaml").write_text("backends:\n  text: source_first\n  audio: source_policy\n  text_bundle_fallback: enabled\n  audio_bundle_fallback: enabled\n", encoding="utf-8")
            (config_dir / "runtime.pre_release.yaml").write_text("backends:\n  text_bundle_fallback: disabled\n  audio_bundle_fallback: disabled\n", encoding="utf-8")
            with patch.object(configuration, "CONFIG_DIR", config_dir), patch.dict(os.environ, {"DEMO_APP_CONFIG_PROFILE": "pre_release"}, clear=False):
                configuration.clear_config_cache()
                backends = configuration.get_config_section("backends")
                self.assertEqual(backends["text"], "source_first")
                self.assertEqual(backends["audio"], "source_policy")
                self.assertEqual(backends["text_bundle_fallback"], "disabled")
                self.assertEqual(backends["audio_bundle_fallback"], "disabled")
                configuration.clear_config_cache()


if __name__ == "__main__":
    unittest.main()
