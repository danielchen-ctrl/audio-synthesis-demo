from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.runtime_bootstrap import bootstrap_runtime_server, prime_runtime_imports, runtime_import_paths
from demo_app.runtime_bridge import get_runtime_server, reset_runtime_server


class RuntimeBridgeRefactorTests(unittest.TestCase):
    def test_runtime_import_paths_include_expected_locations(self) -> None:
        project_root = Path(r'D:\ui_auto_test\demo_app')
        package_root = project_root / 'src' / 'demo_app'
        paths = runtime_import_paths(project_root=project_root, package_root=package_root)
        self.assertEqual(paths[0], project_root / 'src')
        self.assertIn(package_root / 'domains', paths)
        self.assertIn(package_root / 'assets', paths)

    def test_prime_runtime_imports_is_idempotent(self) -> None:
        sentinel = str(ROOT / 'src' / 'demo_app' / 'domains')
        original = list(sys.path)
        try:
            while sentinel in sys.path:
                sys.path.remove(sentinel)
            prime_runtime_imports([Path(sentinel), Path(sentinel)])
            self.assertEqual(sys.path.count(sentinel), 1)
        finally:
            sys.path[:] = original

    def test_bootstrap_runtime_server_calls_dependencies_once(self) -> None:
        fake_module = SimpleNamespace(name='runtime')
        with patch('demo_app.runtime_bootstrap.ensure_runtime_dirs') as ensure_dirs, \
             patch('demo_app.runtime_bootstrap.load_server_module', return_value=fake_module) as load_server, \
             patch('demo_app.runtime_bootstrap.apply_v2_compatibility') as apply_v2, \
             patch('demo_app.runtime_bootstrap.ensure_extract_info_slots_compat') as ensure_slots, \
             patch('demo_app.runtime_bootstrap.os.chdir') as chdir:
            result = bootstrap_runtime_server(project_root=ROOT, package_root=ROOT / 'src' / 'demo_app')
        self.assertIs(result, fake_module)
        ensure_dirs.assert_called_once()
        load_server.assert_called_once()
        apply_v2.assert_called_once()
        ensure_slots.assert_called_once()
        chdir.assert_called_once()

    def test_runtime_bridge_caches_runtime_server(self) -> None:
        fake_module = SimpleNamespace(name='runtime')
        reset_runtime_server()
        with patch('demo_app.runtime_bridge.bootstrap_runtime_server', return_value=fake_module) as bootstrap:
            first = get_runtime_server()
            second = get_runtime_server()
        self.assertIs(first, fake_module)
        self.assertIs(second, fake_module)
        bootstrap.assert_called_once()
        reset_runtime_server()


if __name__ == '__main__':
    unittest.main()
