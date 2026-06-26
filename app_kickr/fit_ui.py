"""FIT-Vergleich in der NiceGUI-Oberflaeche."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from app_kickr.ui_safe import client_alive
from core.fit import (
    compare_profile_to_fit,
    compare_session_to_fit,
    comparison_chart_option,
    load_fit_activity,
)
from core.session.recording_store import RecordingStore
from core.workout.models import Workout


def show_fit_comparison(
    chart: ui.echart,
    workout: Workout,
    fit_path: Path,
    session_dir: Path | None = None,
) -> list[str]:
    if not client_alive(chart):
        return ["UI nicht verbunden."]
    activity = load_fit_activity(fit_path)
    session = None
    if session_dir is not None and (session_dir / "session.json").is_file():
        session = RecordingStore.load_session(session_dir)

    options = comparison_chart_option(workout, activity, session)
    chart._props["options"] = options
    chart.run_chart_method("setOption", options, ":{ notMerge: true, lazyUpdate: true }")

    lines = compare_profile_to_fit(workout, activity).summary_lines()
    if session:
        lines.append("---")
        lines.extend(compare_session_to_fit(session, activity).summary_lines())
    else:
        lines.append("(Keine KICKR-Aufzeichnung — nur Profil vs FIT)")
    return lines
