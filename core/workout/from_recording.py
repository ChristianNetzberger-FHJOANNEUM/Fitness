"""Workout-Profil aus einer KICKR-Aufzeichnung ableiten."""

from __future__ import annotations

from typing import Any

from .models import Workout, WorkoutStep


def _sample_target(sample: dict[str, Any], fallback: int) -> int:
    raw = sample.get("target_power_w")
    if raw is not None:
        return int(raw)
    return int(sample.get("power_w", fallback))


def workout_from_free_session(
    session: dict[str, Any],
    *,
    name: str | None = None,
    min_step_s: int = 5,
) -> Workout:
    """Erzeugt Stufen-Workout aus Ziel-Leistungsaenderungen waehrend freiem Training."""
    samples = session.get("samples") or []
    if not samples:
        raise ValueError("Keine Aufzeichnungsdaten")

    default_name = name or session.get("workout_name") or "Freies Training"
    steps: list[WorkoutStep] = []
    seg_start = float(samples[0]["elapsed_s"])
    seg_target = _sample_target(samples[0], 0)

    for sample in samples[1:]:
        t = float(sample["elapsed_s"])
        target = _sample_target(sample, seg_target)
        if target == seg_target:
            continue
        duration = t - seg_start
        if duration >= min_step_s:
            steps.append(
                WorkoutStep(
                    duration_s=max(1, int(round(duration))),
                    target_power_w=seg_target,
                    label=f"{seg_target} W",
                )
            )
            seg_start = t
            seg_target = target

    final_duration = float(samples[-1]["elapsed_s"]) - seg_start
    if final_duration >= 1:
        steps.append(
            WorkoutStep(
                duration_s=max(1, int(round(final_duration))),
                target_power_w=seg_target,
                label=f"{seg_target} W",
            )
        )

    if not steps:
        avg = int(sum(s.get("power_w", 0) for s in samples) / len(samples))
        total = max(1, int(round(float(samples[-1]["elapsed_s"]))))
        steps.append(WorkoutStep(duration_s=total, target_power_w=avg, label=f"{avg} W"))

    return Workout(
        name=default_name,
        description="Aus freiem Training erzeugt",
        steps=steps,
    )
