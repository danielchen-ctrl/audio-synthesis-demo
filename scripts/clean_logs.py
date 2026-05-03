#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / 'runtime' / 'logs'


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for path in LOG_DIR.glob('*.log'):
        if path.stat().st_size == 0:
            path.unlink()
            removed += 1
    print(f'removed_empty_logs={removed}')


if __name__ == '__main__':
    main()
