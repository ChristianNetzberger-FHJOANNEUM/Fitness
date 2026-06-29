from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DiscoveredHrSensor:
    name: str
    address: str
    rssi: int | None = None


@dataclass
class HrMetrics:
    bpm: int | None = None
    rr_ms: list[int] = field(default_factory=list)
    contact_detected: bool | None = None
    sensor_contact_supported: bool = False
    energy_kj: int | None = None
    updated_at: datetime = field(default_factory=datetime.now)
