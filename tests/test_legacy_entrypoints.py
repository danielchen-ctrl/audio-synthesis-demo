from __future__ import annotations

import importlib
import py_compile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LegacyEntrypointTests(unittest.TestCase):
    def test_root_entrypoints_forward_to_embedded_server(self) -> None:
        embedded_server = importlib.import_module("embedded_server")
        app = importlib.import_module("app")
        run = importlib.import_module("run")
        server = importlib.import_module("server")

        self.assertIs(app.main, embedded_server.main)
        self.assertIs(run.main, embedded_server.main)
        self.assertIs(server.main, embedded_server.main)

    def test_legacy_pre_release_wrapper_compiles(self) -> None:
        py_compile.compile(str(ROOT / "scripts" / "run_pre_release_source_only_check.py"), doraise=True)


if __name__ == "__main__":
    unittest.main()
