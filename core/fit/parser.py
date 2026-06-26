from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from fitparse import FitFile

from core.ftms.models import BikeMetrics


@dataclass
class FitSample:
    elapsed_s: float
    timestamp: datetime
    power_w: float
    cadence_rpm: float
    heart_rate_bpm: int | None = None

    def to_dict(self) -> dict:
        return {
            "elapsed_s": round(self.elapsed_s, 3),
            "timestamp": self.timestamp.isoformat(),
            "power_w": self.power_w,
            "cadence_rpm": round(self.cadence_rpm, 1),
            "heart_rate_bpm": self.heart_rate_bpm,
        }


@dataclass
class FitActivity:
    path: Path
    sport: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    samples: list[FitSample] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        if not self.samples:
            return 0.0
        return self.samples[-1].elapsed_s

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "sport": self.sport,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_s": round(self.duration_s, 3),
            "samples": [s.to_dict() for s in self.samples],
        }


def load_fit_activity(path: Path | str) -> FitActivity:
    fit_path = Path(path)
    fit_file = FitFile(str(fit_path))
    activity = FitActivity(path=fit_path)

    for msg in fit_file.get_messages("session"):
        if msg.get_value("sport"):
            activity.sport = str(msg.get_value("sport"))
        if msg.get_value("start_time"):
            activity.start_time = msg.get_value("start_time")

    records: list[tuple[datetime, dict]] = []
    for record in fit_file.get_messages("record"):
        ts = record.get_value("timestamp")
        if ts is None:
            continue
        power = record.get_value("power")
        cadence = record.get_value("cadence")
        hr = record.get_value("heart_rate")
        records.append(
            (
                ts,
                {
                    "power_w": float(power) if power is not None else 0.0,
                    "cadence_rpm": float(cadence) if cadence is not None else 0.0,
                    "heart_rate_bpm": int(hr) if hr is not None else None,
                },
            )
        )

    if not records:
        return activity

    t0 = records[0][0]
    for ts, values in records:
        elapsed = (ts - t0).total_seconds()
        activity.samples.append(
            FitSample(
                elapsed_s=elapsed,
                timestamp=ts,
                power_w=values["power_w"],
                cadence_rpm=values["cadence_rpm"],
                heart_rate_bpm=values["heart_rate_bpm"],
            )
        )
    activity.end_time = records[-1][0]
    if activity.start_time is None:
        activity.start_time = t0
    return activity
