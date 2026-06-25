from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .constants import (
    FTMS_CONTROL_POINT,
    FTMS_SERVICE,
    INDOOR_BIKE_DATA,
    REQUEST_CONTROL,
    RESPONSE_PREFIX,
    RESULT_SUCCESS,
    SET_TARGET_POWER,
    START_OR_RESUME,
    STOP_OR_PAUSE,
)
from .models import BikeMetrics, DiscoveredTrainer
from .winrt_setup import prepare_winrt_for_bleak


class FtmsError(Exception):
    """FTMS protocol or connection error."""


def parse_indoor_bike_data(data: bytes) -> BikeMetrics:
    """Parse FTMS Indoor Bike Data characteristic (0x2AD2)."""
    if len(data) < 2:
        return BikeMetrics()

    flags = struct.unpack_from("<H", data, 0)[0]
    offset = 2
    metrics = BikeMetrics()

    # Bit 0 ist bei vielen Trainern invertiert: 0 = Instantaneous Speed folgt (uint16, 0.01 km/h).
    if not (flags & 0x0001):
        offset += 2

    if flags & (1 << 1):  # Average Speed
        offset += 2
    if flags & (1 << 2):  # Instantaneous Cadence
        if offset + 2 <= len(data):
            raw = struct.unpack_from("<H", data, offset)[0]
            metrics.cadence_rpm = raw / 2.0
        offset += 2
    if flags & (1 << 3):  # Average Cadence
        offset += 2
    if flags & (1 << 4):  # Total Distance (uint24)
        offset += 3
    if flags & (1 << 5):  # Resistance Level
        if offset + 2 <= len(data):
            raw = struct.unpack_from("<h", data, offset)[0]
            metrics.resistance = raw / 10.0
        offset += 2
    if flags & (1 << 6):  # Instantaneous Power
        if offset + 2 <= len(data):
            metrics.power_w = struct.unpack_from("<h", data, offset)[0]
        offset += 2
    if flags & (1 << 7):  # Average Power
        offset += 2
    if flags & (1 << 8):  # Expended Energy
        offset += 5
    if flags & (1 << 9):  # Heart Rate
        if offset + 1 <= len(data):
            metrics.heart_rate_bpm = data[offset]
        offset += 1

    return metrics


class FtmsClient:
    """Async FTMS client for indoor bikes / smart trainers."""

    def __init__(self) -> None:
        self._client: BleakClient | None = None
        self._device: BLEDevice | None = None
        self._control_response: asyncio.Future[bytes] | None = None
        self._metrics = BikeMetrics()
        self._on_metrics: Callable[[BikeMetrics], None] | None = None
        self._connected = False
        self._has_control = False
        self._control_lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.target_power_w: int | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def has_control(self) -> bool:
        return self._has_control

    @property
    def metrics(self) -> BikeMetrics:
        return self._metrics

    @property
    def device_name(self) -> str:
        if self._device is None:
            return ""
        return self._device.name or self._device.address

    def set_metrics_callback(self, callback: Callable[[BikeMetrics], None] | None) -> None:
        self._on_metrics = callback

    async def scan(self, timeout: float = 8.0) -> list[DiscoveredTrainer]:
        prepare_winrt_for_bleak()
        devices = await BleakScanner.discover(timeout=timeout, service_uuids=[FTMS_SERVICE])
        trainers: list[DiscoveredTrainer] = []
        seen: set[str] = set()
        for device in devices:
            if device.address in seen:
                continue
            seen.add(device.address)
            trainers.append(
                DiscoveredTrainer(
                    name=device.name or "(unbekannt)",
                    address=device.address,
                    rssi=getattr(device, "rssi", None),
                )
            )
        trainers.sort(key=lambda t: t.rssi if t.rssi is not None else -999, reverse=True)
        return trainers

    async def connect(self, address: str) -> None:
        prepare_winrt_for_bleak()
        await self.disconnect()
        self._device = await BleakScanner.find_device_by_address(address, timeout=15.0)
        if self._device is None:
            raise FtmsError(f"Gerät nicht gefunden: {address}")

        self._client = BleakClient(self._device)
        await self._client.connect()
        if not self._client.is_connected:
            raise FtmsError("BLE-Verbindung fehlgeschlagen")

        await self._client.start_notify(INDOOR_BIKE_DATA, self._on_bike_data)
        await self._client.start_notify(FTMS_CONTROL_POINT, self._on_control_point)
        self._loop = asyncio.get_running_loop()
        self._connected = True
        self._has_control = False

    async def disconnect(self) -> None:
        self._has_control = False
        self._connected = False
        self._loop = None
        self.target_power_w = None
        if self._client is not None:
            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            finally:
                self._client = None
        self._device = None
        self._metrics = BikeMetrics()

    async def request_control(self) -> None:
        await self._write_control(bytes([REQUEST_CONTROL]))
        self._has_control = True

    async def start(self) -> None:
        await self._write_control(bytes([START_OR_RESUME]))

    async def stop(self) -> None:
        await self._write_control(bytes([STOP_OR_PAUSE, 0x01]))

    async def set_target_power(self, watts: int) -> None:
        watts = max(0, min(watts, 2000))
        payload = struct.pack("<Bh", SET_TARGET_POWER, watts)
        await self._write_control(payload)
        self.target_power_w = watts

    async def apply_erg_power(self, watts: int) -> None:
        """Training starten/resumieren und Zielleistung setzen (wie manuelles ERG)."""
        if not self._has_control:
            await self.request_control()
        await self.start()
        await self.set_target_power(watts)

    def _on_bike_data(self, _handle: int, data: bytearray) -> None:
        self._metrics = parse_indoor_bike_data(bytes(data))
        if self._on_metrics is not None:
            self._on_metrics(self._metrics)

    def _on_control_point(self, _handle: int, data: bytearray) -> None:
        if self._control_response is None or self._control_response.done():
            return
        result = bytes(data)
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._control_response.set_result, result)
        else:
            self._control_response.set_result(result)

    async def _write_control(self, payload: bytes) -> None:
        if self._client is None or not self._client.is_connected:
            raise FtmsError("Nicht verbunden")

        async with self._control_lock:
            self._control_response = asyncio.get_running_loop().create_future()
            await self._client.write_gatt_char(FTMS_CONTROL_POINT, payload, response=True)

            try:
                response = await asyncio.wait_for(self._control_response, timeout=5.0)
            except asyncio.TimeoutError as exc:
                raise FtmsError("Keine Antwort vom Control Point (Timeout)") from exc
            finally:
                self._control_response = None

            if len(response) >= 3 and response[0] == RESPONSE_PREFIX and response[2] != RESULT_SUCCESS:
                raise FtmsError(f"Control Point abgelehnt: {response.hex()}")
