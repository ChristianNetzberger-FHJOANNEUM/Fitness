from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DiscoveredTrainer:
    name: str
    address: str
    rssi: int | None = None


@dataclass
class BikeMetrics:
    power_w: int | None = None
    cadence_rpm: float | None = None
    resistance: float | None = None
    heart_rate_bpm: int | None = None
    updated_at: datetime = field(default_factory=datetime.now)
