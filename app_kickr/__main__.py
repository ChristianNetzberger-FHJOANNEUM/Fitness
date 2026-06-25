"""Einstieg: python -m app_kickr (aus Repo-Root, venv aktiv)."""
from __future__ import annotations

import sys

# MTA vor matplotlib/pywin32 — sonst STA-Konflikt mit bleak (WinRT).
if sys.platform == "win32":
    sys.coinit_flags = 0

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app_kickr.main_app import run

if __name__ in {"__main__", "__mp_main__"}:
    run()
