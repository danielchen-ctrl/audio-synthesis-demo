#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_guard import main


if __name__ == "__main__":
    print("[DEPRECATED] cleanup_tool.py is a compatibility wrapper. Use 'python scripts/maintenance/project_guard.py' instead.")
    raise SystemExit(main(["cleanup-compat", *sys.argv[1:]]))
