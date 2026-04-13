#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_DIR = ROOT / "scripts" / "maintenance"
if str(MAINTENANCE_DIR) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE_DIR))

from project_guard import main


if __name__ == "__main__":
    raise SystemExit(main())
