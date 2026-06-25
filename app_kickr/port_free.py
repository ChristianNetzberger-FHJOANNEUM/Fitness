"""Port fuer app_kickr freimachen, falls noch ein alter NiceGUI-Prozess lauscht."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from check_ports import (  # noqa: E402
    get_pids_on_port,
    get_process_name_windows,
    kill_process_unix,
    kill_process_windows,
)


def ensure_port_free(port: int) -> None:
    """
    Wenn `port` belegt ist, zugehoerige LISTENING-Prozesse beenden.

    Ueberspringen mit Umgebungsvariable ``KICKR_SKIP_PORT_FREE=1``.
    """
    if not port or port < 1:
        return
    if os.environ.get("KICKR_SKIP_PORT_FREE", "").strip().lower() in ("1", "true", "yes"):
        return

    raw = get_pids_on_port(int(port), listening_only=True)
    mypid = os.getpid()
    pids = [p for p in raw if p != mypid]
    if not pids:
        return

    print(
        f"app_kickr: Port {port} ist belegt (PID(s): {pids}) — beende Prozess(e) …",
        flush=True,
    )
    if sys.platform == "win32":
        for pid in pids:
            name = get_process_name_windows(pid)
            if name:
                print(f"  PID {pid}: {name}", flush=True)

    any_killed = False
    for pid in pids:
        ok = kill_process_windows(pid) if sys.platform == "win32" else kill_process_unix(pid)
        if ok:
            any_killed = True
            print(f"  PID {pid} beendet.", flush=True)
        else:
            print(
                f"  PID {pid} konnte nicht beendet werden (evtl. Admin-Rechte noetig).",
                flush=True,
            )
    if any_killed:
        time.sleep(0.45)
