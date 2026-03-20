#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_app.app import *  # noqa: F401,F403
from demo_app.app import main


if __name__ == '__main__':
    main()
