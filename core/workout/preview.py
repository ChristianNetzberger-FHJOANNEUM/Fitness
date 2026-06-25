from __future__ import annotations

from typing import Any

from .models import Workout


def _workout_y_max(workout: Workout) -> float:
    if not workout.steps:
        return 100.0
    return max(s.target_power_w for s in workout.steps) * 1.1


def workout_chart_option(workout: Workout, progress_s: float | None = None) -> dict[str, Any]:
    """ECharts-Treppenprofil: Zielleistung ueber die Workout-Zeit."""
    if not workout.steps:
        return {
            "title": {"text": workout.name, "left": "center"},
            "xAxis": {"type": "value", "name": "Zeit (s)"},
            "yAxis": {"type": "value", "name": "Watt"},
            "series": [],
        }

    points: list[list[float]] = []
    t = 0.0
    for step in workout.steps:
        points.append([t, float(step.target_power_w)])
        t += step.duration_s
    points.append([t, float(workout.steps[-1].target_power_w)])

    y_max = _workout_y_max(workout)
    series: list[dict[str, Any]] = [
        {
            "id": "workout_profile",
            "name": "Zielleistung",
            "type": "line",
            "step": "end",
            "showSymbol": False,
            "lineStyle": {"width": 2},
            "areaStyle": {"opacity": 0.12},
            "data": points,
        },
    ]
    if progress_s is not None and progress_s >= 0:
        series.append(
            {
                "id": "workout_progress",
                "name": "Fortschritt",
                "type": "line",
                "data": [[float(progress_s), 0.0], [float(progress_s), y_max]],
                "showSymbol": False,
                "silent": True,
                "animation": False,
                "lineStyle": {"color": "#e53935", "width": 2},
            }
        )

    return {
        "title": {"text": workout.name, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 50, "right": 20, "top": 40, "bottom": 40},
        "xAxis": {"type": "value", "name": "Zeit (s)", "min": 0, "max": t},
        "yAxis": {"type": "value", "name": "Watt", "min": 0, "max": y_max},
        "series": series,
    }


def workout_table_rows(workout: Workout) -> list[dict[str, Any]]:
    rows = []
    t = 0
    for i, step in enumerate(workout.steps, start=1):
        rows.append(
            {
                "nr": i,
                "start_s": t,
                "duration_s": step.duration_s,
                "target_power_w": step.target_power_w,
                "label": step.label or f"Schritt {i}",
            }
        )
        t += step.duration_s
    return rows
