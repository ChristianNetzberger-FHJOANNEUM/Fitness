#!/usr/bin/env python3
"""Port 8080 (app_kickr) freimachen — beendet verwaiste NiceGUI-Prozesse."""
from __future__ import annotations

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

sys.argv = ["check_ports.py", "8080", "-k"]
from check_ports import main  # noqa: E402

if __name__ == "__main__":
    print("Port 8080 (app_kickr) freigeben …")
    main()
