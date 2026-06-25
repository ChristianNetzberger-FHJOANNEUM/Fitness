"""
Prueft, welche Prozesse Ports belegen, und kann diese optional beenden.

Verwendung (aus Fitness-Repo-Root):
  python scripts/check_ports.py           # Standard-Port 8080
  python scripts/check_ports.py 8080 -k   # Port freigeben
"""

from __future__ import annotations

import argparse
import subprocess
import sys

DEFAULT_PORTS = [8080]


def get_pids_on_port_windows(port: int, *, listening_only: bool = False) -> list[int]:
    try:
        out = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    pids: set[int] = set()
    port_str = f":{port}"
    for line in out.stdout.splitlines():
        line = line.strip()
        if port_str not in line:
            continue
        is_listen = "LISTENING" in line or "ABH" in line
        is_est = "ESTABLISHED" in line
        if listening_only:
            if not is_listen:
                continue
        elif not (is_listen or is_est):
            continue
        parts = line.split()
        if len(parts) >= 1 and parts[-1].isdigit():
            pids.add(int(parts[-1]))
    return sorted(pids)


def get_pids_on_port_unix(port: int, *, listening_only: bool = False) -> list[int]:
    try:
        if listening_only:
            out = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            out = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True,
                text=True,
                timeout=10,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    pids = []
    for line in out.stdout.strip().splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return sorted(set(pids))


def get_pids_on_port(port: int, *, listening_only: bool = False) -> list[int]:
    if sys.platform == "win32":
        return get_pids_on_port_windows(port, listening_only=listening_only)
    return get_pids_on_port_unix(port, listening_only=listening_only)


def get_process_name_windows(pid: int) -> str:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if out.returncode != 0 or not out.stdout.strip():
        return ""
    parts = out.stdout.strip().split(",")
    if parts:
        return parts[0].strip('"')
    return ""


def kill_process_windows(pid: int) -> bool:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return True
    except Exception:
        return False


def kill_process_unix(pid: int) -> bool:
    try:
        subprocess.run(["kill", "-9", str(pid)], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Ports pruefen und optional freigeben.")
    parser.add_argument(
        "ports",
        nargs="*",
        type=int,
        default=DEFAULT_PORTS,
        help=f"Port(s) (Standard: {DEFAULT_PORTS})",
    )
    parser.add_argument("-k", "--kill", action="store_true", help="Belegende Prozesse beenden")
    parser.add_argument("-q", "--quiet", action="store_true", help="Nur PIDs ausgeben")
    args = parser.parse_args()

    ports = args.ports if isinstance(args.ports, list) else [args.ports]
    any_found = False
    for port in ports:
        pids = get_pids_on_port(port, listening_only=args.kill)
        if not pids:
            if not args.quiet:
                print(f"Port {port}: nicht belegt.")
            continue
        any_found = True
        if args.quiet:
            for pid in pids:
                print(pid)
            continue
        print(f"Port {port} wird belegt von PID(s): {pids}")
        if sys.platform == "win32":
            for pid in pids:
                name = get_process_name_windows(pid)
                if name:
                    print(f"  PID {pid}: {name}")
        if args.kill:
            for pid in pids:
                ok = kill_process_windows(pid) if sys.platform == "win32" else kill_process_unix(pid)
                if ok:
                    print(f"  PID {pid} beendet.")
                else:
                    print(f"  PID {pid} konnte nicht beendet werden.")

    if not any_found and not args.quiet and not args.kill:
        print("Keine der angegebenen Ports ist belegt.")


if __name__ == "__main__":
    main()
