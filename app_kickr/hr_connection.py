"""HF-Brustgurt Verbindungs-Handler."""

from __future__ import annotations

import asyncio
import logging

from nicegui import ui

from core.hr import HrClient, HrMetrics

_logger = logging.getLogger(__name__)


async def scan_hr_sensors(client: HrClient, set_status) -> tuple[list, dict[str, str]]:
    sensors = await client.scan()
    options = {s.address: f"{s.name} ({s.address})" for s in sensors}
    return sensors, options


async def connect_hr_sensor(
    client: HrClient,
    address: str,
    set_status,
) -> None:
    await client.connect(address)
    set_status(f"HF verbunden: {client.device_name}")
    _logger.info("HF connect abgeschlossen, warte auf Pakete …")
    ui.notify(
        "HF-Sensor verbunden. Falls Windows «Gerät koppeln» anzeigt: sofort «Zulassen».",
        type="positive",
    )

    for attempt in range(10):
        await asyncio.sleep(0.3)
        if client.notification_count > 0:
            set_status(f"HF aktiv: {client.device_name} ({client.notification_count} Pakete)")
            _logger.info("HF aktiv nach %.1fs (%d Pakete)", (attempt + 1) * 0.3, client.notification_count)
            return

    ui.notify(
        "Keine HF-Daten — Gurt nass/anlegen? "
        "Falls der H10 in Windows-Bluetooth gekoppelt ist: dort entfernen und erneut verbinden.",
        type="warning",
        timeout=10,
    )
    set_status(f"HF verbunden, warte auf Signal: {client.device_name}")

async def disconnect_hr_sensor(
    client: HrClient,
    hr_plot,
    refresh_hr_label,
    set_status,
) -> None:
    await client.disconnect()
    if hr_plot is not None:
        hr_plot.clear()
    refresh_hr_label(HrMetrics())
    set_status("HF-Sensor getrennt.")
