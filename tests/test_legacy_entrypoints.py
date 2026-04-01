from __future__ import annotations

import importlib
import py_compile
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class LegacyEntrypointTests(unittest.TestCase):
    def test_root_server_entrypoint_forwards_to_package_server(self) -> None:
        embedded_server = importlib.import_module("demo_app.embedded_server_main")
        server = importlib.import_module("server")

        self.assertIs(server.main, embedded_server.main)

    def test_legacy_pre_release_wrapper_compiles(self) -> None:
        py_compile.compile(str(ROOT / "scripts" / "run_pre_release_source_only_check.py"), doraise=True)


if __name__ == "__main__":
    unittest.main()
