from __future__ import annotations

"""Deprecated compatibility wrapper.

Historically this script executed an older source-first runtime path under
`src/demo_app`. The current repository ships and validates the embedded demo
runtime instead, so this script now forwards to the maintained pre-release gate
entrypoint.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_pre_release_ci_gate import main as gate_main


def main(argv: list[str] | None = None) -> int:
    print(
        "[DEPRECATED] scripts/run_pre_release_source_only_check.py 已切换为兼容入口。"
        "请优先使用 scripts/run_pre_release_ci_gate.py。"
    )
    return gate_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
