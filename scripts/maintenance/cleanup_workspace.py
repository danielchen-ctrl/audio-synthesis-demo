#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    removed_dirs = 0
    removed_files = 0
    for cache_dir in ROOT.rglob('__pycache__'):
        shutil.rmtree(cache_dir, ignore_errors=True)
        removed_dirs += 1
    for pyc in ROOT.rglob('*.pyc'):
        pyc.unlink(missing_ok=True)
        removed_files += 1
    print(f'removed_cache_dirs={removed_dirs}')
    print(f'removed_pyc_files={removed_files}')


if __name__ == '__main__':
    main()
