"""CLI-Test fuer Polar H10 / BLE Heart Rate (ohne NiceGUI).

Beispiele:
    python -m core.hr scan
    python -m core.hr connect AA:BB:CC:DD:EE:FF
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .client import HrClient, HrError
from .models import HrMetrics


def _print_metrics(metrics: HrMetrics, *, count: int) -> None:
    bpm = metrics.bpm if metrics.bpm is not None else "—"
    contact = ""
    if metrics.sensor_contact_supported:
        contact = " Kontakt OK" if metrics.contact_detected else " KEIN Kontakt"
    rr = f" RR={metrics.rr_ms}" if metrics.rr_ms else ""
    print(f"[{count:4d}] HF {bpm} bpm{contact}{rr}")


async def _scan(timeout: float) -> int:
    client = HrClient()
    sensors = await client.scan(timeout=timeout)
    if not sensors:
        print("Keine HF-Sensoren gefunden.")
        return 1
    for sensor in sensors:
        rssi = f" {sensor.rssi} dBm" if sensor.rssi is not None else ""
        print(f"{sensor.address}  {sensor.name}{rssi}")
    return 0


async def _connect(address: str, duration: float) -> int:
    client = HrClient()
    count = 0

    def on_metrics(metrics: HrMetrics) -> None:
        nonlocal count
        count += 1
        _print_metrics(metrics, count=count)

    client.set_metrics_callback(on_metrics)
    try:
        await client.connect(address)
    except HrError as exc:
        print(f"Verbindung fehlgeschlagen: {exc}", file=sys.stderr)
        return 1

    print(f"Verbunden: {client.device_name} ({address})")
    print("Warte auf HF-Pakete (Strg+C zum Beenden) …")
    try:
        await asyncio.sleep(duration)
    except asyncio.CancelledError:
        pass
    finally:
        await client.disconnect()

    if count == 0:
        print(
            "\nKeine Pakete empfangen. Gurt nass/anlegen? "
            "Falls in Windows gekoppelt: Geraet dort entfernen.",
            file=sys.stderr,
        )
        return 2
    print(f"\n{count} Pakete empfangen.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BLE Heart Rate Sensor Test")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="HF-Sensoren scannen")
    scan_p.add_argument("--timeout", type=float, default=8.0)

    conn_p = sub.add_parser("connect", help="Mit Sensor verbinden und HF anzeigen")
    conn_p.add_argument("address", help="BLE-Adresse (z. B. AA:BB:CC:DD:EE:FF)")
    conn_p.add_argument("--duration", type=float, default=30.0, help="Sekunden lauschen")

    args = parser.parse_args(argv)
    if args.command == "scan":
        return asyncio.run(_scan(args.timeout))
    if args.command == "connect":
        return asyncio.run(_connect(args.address, args.duration))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
