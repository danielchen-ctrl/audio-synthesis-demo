from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXTRA_PATHS = [
    ROOT / 'src',
    ROOT / 'src' / 'demo_app',
    ROOT / 'src' / 'demo_app' / 'domains',
    ROOT / 'src' / 'demo_app' / 'assets',
]

for path in EXTRA_PATHS:
    if path.exists():
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
