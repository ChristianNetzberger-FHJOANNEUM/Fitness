from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from core.ftms.models import BikeMetrics


@dataclass
class MetricsBuffer:
    """Ringpuffer fuer Strip-Charts (Leistung, Kadenz, HF ueber Zeit)."""

    max_points: int | None = 600
    times: deque[float] = field(default_factory=deque)
    power_w: deque[float] = field(default_factory=deque)
    cadence_rpm: deque[float] = field(default_factory=deque)
    hr_times: deque[float] = field(default_factory=deque)
    heart_rate_bpm: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.max_points is None:
            self.times = deque()
            self.power_w = deque()
            self.cadence_rpm = deque()
            self.hr_times = deque()
            self.heart_rate_bpm = deque()
        else:
            self.times = deque(maxlen=self.max_points)
            self.power_w = deque(maxlen=self.max_points)
            self.cadence_rpm = deque(maxlen=self.max_points)
            self.hr_times = deque(maxlen=self.max_points)
            self.heart_rate_bpm = deque(maxlen=self.max_points)

    def clear(self) -> None:
        self.times.clear()
        self.power_w.clear()
        self.cadence_rpm.clear()
        self.hr_times.clear()
        self.heart_rate_bpm.clear()

    def append(self, elapsed_s: float, metrics: BikeMetrics) -> None:
        self.times.append(elapsed_s)
        self.power_w.append(float(metrics.power_w) if metrics.power_w is not None else 0.0)
        self.cadence_rpm.append(
            float(metrics.cadence_rpm) if metrics.cadence_rpm is not None else 0.0
        )

    def append_hr(self, elapsed_s: float, bpm: int) -> None:
        self.hr_times.append(elapsed_s)
        self.heart_rate_bpm.append(float(bpm))

    def latest_delta(self) -> tuple[list[float], list[list[float]], list[list[float]]] | None:
        """Letzten Punkt fuer inkrementelles line_plot.push."""
        if not self.times:
            return None
        t = self.times[-1]
        return [t], [[self.power_w[-1]]], [[self.cadence_rpm[-1]]]


@dataclass
class LiveSession:
    buffer: MetricsBuffer = field(default_factory=MetricsBuffer)
    _started_at: float | None = None
    _paused_at: float | None = None
    _paused_total_s: float = 0.0
    _frozen_elapsed_s: float = 0.0
    _last_pushed_index: int = 0
    _last_hr_pushed_index: int = 0

    @property
    def active(self) -> bool:
        return self._started_at is not None

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    @property
    def elapsed_s(self) -> float:
        if self._started_at is None:
            return 0.0
        now = time.time()
        elapsed = now - self._started_at - self._paused_total_s
        if self._paused_at is not None:
            elapsed -= now - self._paused_at
        return max(0.0, elapsed)

    @property
    def display_elapsed_s(self) -> float:
        """Laufzeit fuer Anzeige — bleibt nach stop() auf dem letzten Wert."""
        if self.active:
            return self.elapsed_s
        return self._frozen_elapsed_s

    def start(self, *, unlimited: bool = False) -> None:
        self.reset()
        if unlimited:
            self.buffer = MetricsBuffer(max_points=None)
        else:
            self.buffer = MetricsBuffer(max_points=600)
        self._started_at = time.time()

    def pause(self) -> None:
        if self._started_at is None or self._paused_at is not None:
            return
        self._paused_at = time.time()

    def resume(self) -> None:
        if self._paused_at is None:
            return
        self._paused_total_s += time.time() - self._paused_at
        self._paused_at = None

    def stop(self) -> None:
        if self._started_at is not None:
            self._frozen_elapsed_s = self.elapsed_s
        self._started_at = None
        self._paused_at = None

    def reset(self) -> None:
        self._started_at = None
        self._paused_at = None
        self._paused_total_s = 0.0
        self._frozen_elapsed_s = 0.0
        self._last_pushed_index = 0
        self._last_hr_pushed_index = 0
        self.buffer.clear()

    def on_metrics(self, metrics: BikeMetrics) -> None:
        if self._started_at is None or self._paused_at is not None:
            return
        self.buffer.append(self.elapsed_s, metrics)

    def on_hr(self, bpm: int) -> None:
        if self._started_at is None or self._paused_at is not None:
            return
        self.buffer.append_hr(self.elapsed_s, bpm)

    def drain_for_plot(self) -> tuple[list[float], list[float], list[float]] | None:
        """Neue Punkte seit letztem Plot-Update (fuer Batch-Push)."""
        n = len(self.buffer.times)
        if n <= self._last_pushed_index:
            return None
        start = self._last_pushed_index
        self._last_pushed_index = n
        times = list(self.buffer.times)[start:n]
        power = list(self.buffer.power_w)[start:n]
        cadence = list(self.buffer.cadence_rpm)[start:n]
        return times, power, cadence

    def drain_hr_for_plot(self) -> tuple[list[float], list[float]] | None:
        n = len(self.buffer.hr_times)
        if n <= self._last_hr_pushed_index:
            return None
        start = self._last_hr_pushed_index
        self._last_hr_pushed_index = n
        times = list(self.buffer.hr_times)[start:n]
        hr = list(self.buffer.heart_rate_bpm)[start:n]
        return times, hr
