"""Verbindungs- und ERG-Handler."""

from __future__ import annotations

from nicegui import ui

from core.ftms import BikeMetrics, FtmsClient
from core.ftms.client import FtmsError
from core.session import LiveSession


async def scan_trainers(client: FtmsClient, set_status) -> list:
    trainers = await client.scan()
    options = {t.address: f"{t.name} ({t.address})" for t in trainers}
    return trainers, options


async def connect_trainer(
    client: FtmsClient,
    session: LiveSession,
    address: str,
    power_plot,
    cadence_plot,
    set_status,
    refresh_live_labels,
) -> None:
    await client.connect(address)
    await client.request_control()
    await client.start()
    session.start()
    power_plot.clear()
    cadence_plot.clear()
    refresh_live_labels(BikeMetrics())
    set_status(f"Verbunden: {client.device_name}")
    ui.notify("FTMS-Verbindung steht.", type="positive")


async def disconnect_trainer(
    client: FtmsClient,
    session: LiveSession,
    power_plot,
    cadence_plot,
    refresh_live_labels,
    set_status,
    cancel_workout,
) -> None:
    cancel_workout()
    await client.disconnect()
    session.stop()
    power_plot.clear()
    cadence_plot.clear()
    refresh_live_labels(BikeMetrics())
    set_status("Getrennt.")


async def set_manual_erg(client: FtmsClient, watts: int, set_status) -> None:
    if not client.connected:
        raise FtmsError("Nicht verbunden")
    await client.apply_erg_power(watts)
    set_status(f"ERG {watts} W — Zielwatt gilt beim Treten")


async def stop_trainer(client: FtmsClient, set_status) -> None:
    if client.connected:
        await client.stop()
    set_status("Trainer gestoppt.")
