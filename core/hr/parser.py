from __future__ import annotations

import struct

from .models import HrMetrics


def parse_heart_rate_measurement(data: bytes) -> HrMetrics:
    """Parse BLE Heart Rate Measurement (0x2A37). RR in Millisekunden."""
    if not data:
        return HrMetrics()

    flags = data[0]
    offset = 1
    metrics = HrMetrics()

    metrics.sensor_contact_supported = bool(flags & 0x02)
    if metrics.sensor_contact_supported:
        metrics.contact_detected = bool(flags & 0x04)

    if flags & 0x01:
        if offset + 2 > len(data):
            return metrics
        metrics.bpm = struct.unpack_from("<H", data, offset)[0]
        offset += 2
    else:
        if offset + 1 > len(data):
            return metrics
        metrics.bpm = data[offset]
        offset += 1

    if flags & 0x08:
        if offset + 2 > len(data):
            return metrics
        metrics.energy_kj = struct.unpack_from("<H", data, offset)[0]
        offset += 2

    if flags & 0x10:
        rr_ms: list[int] = []
        while offset + 2 <= len(data):
            raw = struct.unpack_from("<H", data, offset)[0]
            rr_ms.append(int(round(raw * 1000.0 / 1024.0)))
            offset += 2
        metrics.rr_ms = rr_ms

    return metrics
