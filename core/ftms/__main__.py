"""CLI zum Debuggen ohne Browser: python -m core.ftms scan"""
from __future__ import annotations

import sys

if sys.platform == "win32":
    sys.coinit_flags = 0

import argparse
import asyncio
import sys

from core.ftms import FtmsClient
from core.ftms.client import FtmsError


async def cmd_scan(timeout: float) -> int:
    client = FtmsClient()
    trainers = await client.scan(timeout=timeout)
    if not trainers:
        print("Keine FTMS-Trainer gefunden.")
        return 1
    for t in trainers:
        rssi = f"  RSSI={t.rssi}" if t.rssi is not None else ""
        print(f"  {t.name:30}  {t.address}{rssi}")
    return 0


async def cmd_erg(address: str, watts: int, duration: float) -> int:
    client = FtmsClient()

    def on_metrics(m):
        p = m.power_w if m.power_w is not None else "—"
        c = f"{m.cadence_rpm:.0f}" if m.cadence_rpm is not None else "—"
        print(f"\r  {p} W   {c} rpm   ", end="", flush=True)

    client.set_metrics_callback(on_metrics)
    try:
        print(f"Verbinde mit {address} …")
        await client.connect(address)
        await client.request_control()
        await client.start()
        print(f"ERG {watts} W fuer {duration:.0f} s (Ctrl+C zum Abbrechen)")
        await client.set_target_power(watts)
        await asyncio.sleep(duration)
        await client.stop()
        print("\nGestoppt.")
        return 0
    except (FtmsError, KeyboardInterrupt) as exc:
        print(f"\n{exc}")
        return 1
    finally:
        await client.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FTMS CLI (KICKR Debug)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="FTMS-Trainer scannen")
    p_scan.add_argument("--timeout", type=float, default=8.0)

    p_erg = sub.add_parser("erg", help="ERG-Test")
    p_erg.add_argument("--address", required=True, help="BLE-Adresse")
    p_erg.add_argument("--watts", type=int, default=150)
    p_erg.add_argument("--duration", type=float, default=60.0)

    args = parser.parse_args(argv)
    if args.command == "scan":
        return asyncio.run(cmd_scan(args.timeout))
    if args.command == "erg":
        return asyncio.run(cmd_erg(args.address, args.watts, args.duration))
    return 1


if __name__ == "__main__":
    sys.exit(main())
