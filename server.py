#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Redirect to server_platform.py (single unified server)

from __future__ import annotations
import runpy, sys
from pathlib import Path

sys.argv[0] = str(Path(__file__).with_name("server_platform.py"))
runpy.run_path(sys.argv[0], run_name="__main__")
