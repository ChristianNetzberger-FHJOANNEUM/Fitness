from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.workout.models import Workout

from .parser import FitActivity, FitSample


def target_power_at(workout: Workout, elapsed_s: float) -> int:
    if not workout.steps:
        return 0
    t = 0.0
    for step in workout.steps:
        if elapsed_s < t + step.duration_s:
            return step.target_power_w
        t += step.duration_s
    return workout.steps[-1].target_power_w


@dataclass
class ComparisonStats:
    mode: str
    sample_count: int
    duration_fit_s: float
    duration_ref_s: float
    mean_abs_error_w: float
    max_abs_error_w: float
    mean_power_fit_w: float
    mean_power_ref_w: float
    within_10w_pct: float

    def summary_lines(self) -> list[str]:
        return [
            f"Modus: {self.mode}",
            f"FIT-Dauer: {self.duration_fit_s:.0f} s | Referenz: {self.duration_ref_s:.0f} s",
            f"Mittlere Abweichung: {self.mean_abs_error_w:.1f} W (max {self.max_abs_error_w:.0f} W)",
            f"Mittlere Leistung FIT: {self.mean_power_fit_w:.0f} W | Referenz: {self.mean_power_ref_w:.0f} W",
            f"Innerhalb ±10 W: {self.within_10w_pct:.0f} %",
        ]


def _stats_from_pairs(mode: str, pairs: list[tuple[float, float]], duration_fit: float, duration_ref: float) -> ComparisonStats:
    if not pairs:
        return ComparisonStats(
            mode=mode,
            sample_count=0,
            duration_fit_s=duration_fit,
            duration_ref_s=duration_ref,
            mean_abs_error_w=0.0,
            max_abs_error_w=0.0,
            mean_power_fit_w=0.0,
            mean_power_ref_w=0.0,
            within_10w_pct=0.0,
        )
    errors = [abs(fit - ref) for fit, ref in pairs]
    within = sum(1 for e in errors if e <= 10.0) / len(errors) * 100.0
    fit_vals = [p[0] for p in pairs]
    ref_vals = [p[1] for p in pairs]
    return ComparisonStats(
        mode=mode,
        sample_count=len(pairs),
        duration_fit_s=duration_fit,
        duration_ref_s=duration_ref,
        mean_abs_error_w=sum(errors) / len(errors),
        max_abs_error_w=max(errors),
        mean_power_fit_w=sum(fit_vals) / len(fit_vals),
        mean_power_ref_w=sum(ref_vals) / len(ref_vals),
        within_10w_pct=within,
    )


def _resample_ref_power(workout: Workout, fit_samples: list[FitSample]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for sample in fit_samples:
        if sample.power_w <= 0 and sample.cadence_rpm <= 0:
            continue
        ref = float(target_power_at(workout, sample.elapsed_s))
        pairs.append((sample.power_w, ref))
    return pairs


def _resample_session_power(session: dict, fit_samples: list[FitSample]) -> list[tuple[float, float]]:
    kickr = session.get("samples") or []
    if not kickr:
        return []
    pairs: list[tuple[float, float]] = []
    ki = 0
    for fit in fit_samples:
        if fit.power_w <= 0 and fit.cadence_rpm <= 0:
            continue
        while ki + 1 < len(kickr) and kickr[ki + 1]["elapsed_s"] <= fit.elapsed_s:
            ki += 1
        kickr_power = float(kickr[ki]["power_w"])
        pairs.append((fit.power_w, kickr_power))
    return pairs


def compare_profile_to_fit(workout: Workout, activity: FitActivity) -> ComparisonStats:
    pairs = _resample_ref_power(workout, activity.samples)
    return _stats_from_pairs(
        "Workout-Profil vs FIT",
        pairs,
        activity.duration_s,
        float(workout.total_duration_s),
    )


def compare_session_to_fit(session: dict, activity: FitActivity) -> ComparisonStats:
    pairs = _resample_session_power(session, activity.samples)
    duration_ref = float(session.get("duration_s") or 0)
    return _stats_from_pairs(
        "KICKR-Aufzeichnung vs FIT",
        pairs,
        activity.duration_s,
        duration_ref,
    )


def comparison_chart_option(
    workout: Workout,
    activity: FitActivity,
    session: dict | None = None,
) -> dict[str, Any]:
    from core.workout.preview import _workout_y_max, workout_chart_option

    base = workout_chart_option(workout, progress_s=None)
    y_max = _workout_y_max(workout)

    fit_points = [[s.elapsed_s, s.power_w] for s in activity.samples if s.power_w > 0 or s.cadence_rpm > 0]
    base["series"].append(
        {
            "id": "fit_power",
            "name": "FIT Leistung",
            "type": "line",
            "showSymbol": False,
            "lineStyle": {"width": 1.5, "color": "#ff9800"},
            "data": fit_points,
        }
    )

    if session and session.get("samples"):
        kickr_points = [
            [s["elapsed_s"], s["power_w"]]
            for s in session["samples"]
            if s.get("power_w", 0) > 0 or s.get("cadence_rpm", 0) > 0
        ]
        base["series"].append(
            {
                "id": "kickr_power",
                "name": "KICKR Aufzeichnung",
                "type": "line",
                "showSymbol": False,
                "lineStyle": {"width": 1.5, "color": "#43a047"},
                "data": kickr_points,
            }
        )
        y_max = max(
            y_max,
            max((p[1] for p in kickr_points), default=0) * 1.1,
            max((p[1] for p in fit_points), default=0) * 1.1,
        )

    base["yAxis"]["max"] = y_max
    base["legend"] = {"data": [s["name"] for s in base["series"]], "top": 0}
    base["title"]["text"] = f"{workout.name} — Vergleich"
    return base
