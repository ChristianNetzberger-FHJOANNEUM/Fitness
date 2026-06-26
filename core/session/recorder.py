from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.ftms.models import BikeMetrics
from core.workout.models import Workout


@dataclass
class RecordedSample:
    elapsed_s: float
    power_w: float
    cadence_rpm: float
    target_power_w: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "elapsed_s": round(self.elapsed_s, 3),
            "power_w": self.power_w,
            "cadence_rpm": round(self.cadence_rpm, 1),
            "target_power_w": self.target_power_w,
        }


@dataclass
class SessionRecorder:
    """Unbegrenzte Aufzeichnung fuer JSON-Export (unabhaengig vom Strip-Chart-Ringpuffer)."""

    samples: list[RecordedSample] = field(default_factory=list)
    workout_id: str = ""
    workout_name: str = ""
    trigger: str = ""
    trainer_name: str = ""
    trainer_address: str = ""
    _started_at_mono: float | None = None
    _paused_at_mono: float | None = None
    _paused_total_s: float = 0.0
    recorded_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self._started_at_mono is not None and self.ended_at is None

    @property
    def paused(self) -> bool:
        return self._paused_at_mono is not None

    def _elapsed_s(self) -> float:
        if self._started_at_mono is None:
            return 0.0
        elapsed = time.monotonic() - self._started_at_mono - self._paused_total_s
        if self._paused_at_mono is not None:
            elapsed -= time.monotonic() - self._paused_at_mono
        return max(0.0, elapsed)

    @property
    def duration_s(self) -> float:
        if self._started_at_mono is None:
            return 0.0
        if self.ended_at and self.recorded_at:
            return (self.ended_at - self.recorded_at).total_seconds()
        return self._elapsed_s()

    def start(
        self,
        *,
        workout_id: str,
        workout: Workout,
        trigger: str,
        trainer_name: str = "",
        trainer_address: str = "",
    ) -> None:
        self.samples.clear()
        self.workout_id = workout_id
        self.workout_name = workout.name
        self.trigger = trigger
        self.trainer_name = trainer_name
        self.trainer_address = trainer_address
        self.recorded_at = datetime.now().astimezone()
        self.ended_at = None
        self._paused_at_mono = None
        self._paused_total_s = 0.0
        self._started_at_mono = time.monotonic()

    def pause(self) -> None:
        if self.active and self._paused_at_mono is None:
            self._paused_at_mono = time.monotonic()

    def resume(self) -> None:
        if self._paused_at_mono is not None:
            self._paused_total_s += time.monotonic() - self._paused_at_mono
            self._paused_at_mono = None

    def stop(self) -> None:
        if self._started_at_mono is None:
            return
        self.ended_at = datetime.now().astimezone()

    def reset(self) -> None:
        self.samples.clear()
        self._started_at_mono = None
        self._paused_at_mono = None
        self._paused_total_s = 0.0
        self.recorded_at = None
        self.ended_at = None

    def append(self, metrics: BikeMetrics, target_power_w: int | None = None) -> None:
        if not self.active or self._paused_at_mono is not None:
            return
        if self._started_at_mono is None:
            return
        elapsed_s = self._elapsed_s()
        self.samples.append(
            RecordedSample(
                elapsed_s=elapsed_s,
                power_w=float(metrics.power_w) if metrics.power_w is not None else 0.0,
                cadence_rpm=float(metrics.cadence_rpm) if metrics.cadence_rpm is not None else 0.0,
                target_power_w=target_power_w,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        if self.recorded_at is None:
            raise ValueError("Recorder wurde nicht gestartet")
        ended = self.ended_at or datetime.now().astimezone()
        return {
            "format_version": 1,
            "recorded_at": self.recorded_at.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_s": round(self.duration_s, 3),
            "trigger": self.trigger,
            "workout_id": self.workout_id,
            "workout_name": self.workout_name,
            "trainer": {
                "name": self.trainer_name,
                "address": self.trainer_address,
            },
            "samples": [s.to_dict() for s in self.samples],
        }
