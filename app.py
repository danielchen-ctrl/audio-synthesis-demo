#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Legacy desktop entrypoint kept as a thin compatibility wrapper.

The previous `app.py -> src/demo_app/app.py` chain no longer exists in this
checkout. We keep this file so older local habits and shortcuts still work,
but route everything to the current embedded demo server implementation.
"""

from embedded_server import *  # noqa: F401,F403
from embedded_server import main


if __name__ == "__main__":
    main()
