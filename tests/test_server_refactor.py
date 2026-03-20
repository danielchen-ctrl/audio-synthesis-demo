from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.app_state import AppState
from demo_app.server import make_app


class ServerRefactorTests(unittest.TestCase):
    def test_make_app_builds_explicit_routes_and_state(self) -> None:
        app = make_app()
        self.assertIsInstance(app.settings["app_state"], AppState)
        self.assertIs(app.settings["dialogue_cache"], app.settings["app_state"].dialogue_cache)
        route_patterns = [rule.matcher.regex.pattern for rule in app.wildcard_router.rules]
        self.assertEqual(
            route_patterns,
            [
                "/$",
                "/api/generate_text$",
                "/api/generate_audio$",
                "/api/download$",
                "/api/read_debug_file$",
                "/static/(.*)$",
            ],
        )


if __name__ == "__main__":
    unittest.main()
