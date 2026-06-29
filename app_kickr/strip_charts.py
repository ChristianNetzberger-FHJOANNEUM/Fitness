"""Hilfen fuer Live-Strip-Charts (Y-Achse, Zeitformat)."""

from __future__ import annotations

from dataclasses import dataclass


def format_elapsed_hms(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass
class StripChartPeakTracker:
    """Y-Max bleibt am bisherigen Peak kleben; Y-Min ist 0."""

    peak_power: float = 0.0
    peak_cadence: float = 0.0
    peak_hr: float = 0.0
    min_power_ymax: float = 150.0
    min_cadence_ymax: float = 100.0
    min_hr_ymax: float = 160.0
    headroom: float = 1.08

    def reset(self) -> None:
        self.peak_power = 0.0
        self.peak_cadence = 0.0
        self.peak_hr = 0.0

    def power_ylim(self, values: list[float]) -> tuple[float, float]:
        if values:
            self.peak_power = max(self.peak_power, max(values))
        ymax = self.min_power_ymax
        if self.peak_power > 0:
            ymax = max(ymax, self.peak_power * self.headroom)
        return (0.0, ymax)

    def hr_ylim(self, values: list[float]) -> tuple[float, float]:
        if values:
            self.peak_hr = max(self.peak_hr, max(values))
        ymax = self.min_hr_ymax
        if self.peak_hr > 0:
            ymax = max(ymax, self.peak_hr * self.headroom)
        return (0.0, ymax)

    def cadence_ylim(self, values: list[float]) -> tuple[float, float]:
        if values:
            self.peak_cadence = max(self.peak_cadence, max(values))
        ymax = self.min_cadence_ymax
        if self.peak_cadence > 0:
            ymax = max(ymax, self.peak_cadence * self.headroom)
        return (0.0, ymax)
