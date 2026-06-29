from __future__ import annotations

import asyncio
import logging
import warnings
from collections.abc import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from core.ftms.winrt_setup import prepare_winrt_for_bleak

from .constants import HEART_RATE_MEASUREMENT, HEART_RATE_SERVICE
from .models import DiscoveredHrSensor, HrMetrics
from .parser import parse_heart_rate_measurement

_logger = logging.getLogger(__name__)


def _device_rssi(device: BLEDevice) -> int | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return getattr(device, "rssi", None)


class HrError(Exception):
    """Heart Rate BLE connection or parse error."""


class HrClient:
    """BLE Heart Rate client (z. B. Polar H10)."""

    def __init__(self) -> None:
        self._client: BleakClient | None = None
        self._device: BLEDevice | None = None
        self._metrics = HrMetrics()
        self._on_metrics: Callable[[HrMetrics], None] | None = None
        self._on_disconnected: Callable[[], None] | None = None
        self._connected = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self.notification_count = 0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def link_up(self) -> bool:
        if not self._connected or self._client is None:
            return False
        try:
            return bool(self._client.is_connected)
        except Exception:
            return False

    @property
    def metrics(self) -> HrMetrics:
        return self._metrics

    @property
    def device_name(self) -> str:
        if self._device is None:
            return ""
        return self._device.name or self._device.address

    def set_metrics_callback(self, callback: Callable[[HrMetrics], None] | None) -> None:
        self._on_metrics = callback

    def set_disconnected_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_disconnected = callback

    def _handle_ble_disconnect(self, _client: BleakClient) -> None:
        was_connected = self._connected
        self._connected = False
        if not was_connected or self._on_disconnected is None:
            return
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._on_disconnected)
        else:
            self._on_disconnected()

    async def scan(self, timeout: float = 8.0) -> list[DiscoveredHrSensor]:
        prepare_winrt_for_bleak()
        devices = await BleakScanner.discover(timeout=timeout, service_uuids=[HEART_RATE_SERVICE])
        sensors: list[DiscoveredHrSensor] = []
        seen: set[str] = set()
        for device in devices:
            if device.address in seen:
                continue
            seen.add(device.address)
            sensors.append(
                DiscoveredHrSensor(
                    name=device.name or "(unbekannt)",
                    address=device.address,
                    rssi=_device_rssi(device),
                )
            )
        sensors.sort(key=lambda s: s.rssi if s.rssi is not None else -999, reverse=True)
        return sensors

    async def connect(self, address: str) -> None:
        prepare_winrt_for_bleak()
        await self.disconnect()
        self._device = await BleakScanner.find_device_by_address(address, timeout=15.0)
        if self._device is None:
            raise HrError(f"HF-Sensor nicht gefunden: {address}")

        self._loop = asyncio.get_running_loop()
        self._client = BleakClient(
            self._device,
            timeout=30.0,
            services=[HEART_RATE_SERVICE],
            disconnected_callback=self._handle_ble_disconnect,
            winrt={"use_cached_services": False},
        )
        try:
            await self._client.connect(timeout=30.0)
        except Exception as exc:
            await self.disconnect()
            msg = str(exc).strip() or type(exc).__name__
            raise HrError(
                f"BLE-Verbindung fehlgeschlagen: {msg}. "
                "Windows-Kopplung abgelehnt oder abgelaufen? "
                "Gurt in Bluetooth-Einstellungen entfernen und erneut verbinden."
            ) from exc

        await self._client.start_notify(HEART_RATE_MEASUREMENT, self._on_hr_data)
        self.notification_count = 0
        self._connected = True
        _logger.info("HF verbunden: %s", self.device_name)

    def mark_disconnected(self) -> None:
        self._connected = False

    async def disconnect(self) -> None:
        self._connected = False
        self._loop = None
        if self._client is not None:
            try:
                if self._client.is_connected:
                    try:
                        await self._client.stop_notify(HEART_RATE_MEASUREMENT)
                    except Exception:
                        pass
                    await self._client.disconnect()
            except Exception as exc:
                _logger.warning("HF disconnect: %s", exc)
            finally:
                self._client = None
        self._device = None
        self._metrics = HrMetrics()
        self.notification_count = 0

    def _dispatch_metrics(self) -> None:
        if self._on_metrics is not None:
            self._on_metrics(self._metrics)

    def _on_hr_data(self, _handle: int, data: bytearray) -> None:
        self.notification_count += 1
        self._metrics = parse_heart_rate_measurement(bytes(data))
        if self._on_metrics is None:
            return
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._dispatch_metrics)
        else:
            self._dispatch_metrics()
