"""Hilfsfunktionen fuer Workout-Tabelle, Profil-Graph und Schritt-Editor."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from app_kickr.ui_safe import client_alive
from core.workout.models import Workout, WorkoutStep
from core.workout.preview import workout_chart_option, workout_table_rows

SUMMARY_COLUMNS = [
    {"name": "nr", "label": "#", "field": "nr"},
    {"name": "start_s", "label": "Start (s)", "field": "start_s"},
    {"name": "duration_s", "label": "Dauer (s)", "field": "duration_s"},
    {"name": "target_power_w", "label": "Watt", "field": "target_power_w"},
    {"name": "label", "label": "Label", "field": "label"},
]


def _read_int(el: ui.element) -> int:
    if hasattr(el, "sanitize"):
        el.sanitize()
    raw = el.value
    if raw is None or raw == "":
        return 0
    return int(float(raw))


def _read_str(el: ui.element) -> str:
    return str(el.value or "")


def refresh_workout_chart(
    chart: ui.echart,
    workout: Workout,
    progress_s: float | None = None,
    *,
    full_replace: bool = False,
) -> None:
    """Profil-Graph setzen. Bei Fortschritt immer komplettes setOption (partielle Updates loeschen das Profil)."""
    if not client_alive(chart):
        return
    options = workout_chart_option(workout, progress_s=progress_s)
    chart._props["options"] = options
    if full_replace or progress_s is not None:
        chart.run_chart_method("setOption", options, ":{ notMerge: true, lazyUpdate: true }")
    else:
        chart.update()


def update_workout_progress_line(chart: ui.echart, workout: Workout, progress_s: float) -> None:
    refresh_workout_chart(chart, workout, progress_s=progress_s)


def refresh_workout_summary(host: ui.column, workout: Workout) -> ui.table:
    """Uebersichtstabelle neu aufbauen (zuverlaessiger als rows-Update bei QTable)."""
    host.clear()
    with host:
        return ui.table(
            columns=SUMMARY_COLUMNS,
            rows=workout_table_rows(workout),
            row_key="nr",
        ).classes("w-full")


def build_step_editor(
    workout: Workout,
    host: ui.column,
    on_change: Callable[[], None],
    sync_registry: dict | None = None,
) -> Callable[[], None]:
    """Schritt-Zeilen im host-Container neu aufbauen. Gibt sync_from_ui zurueck."""

    host.clear()
    fields: list[dict[str, ui.element]] = []

    def sync_from_ui() -> None:
        for i, row in enumerate(fields):
            if i >= len(workout.steps):
                break
            workout.steps[i].duration_s = _read_int(row["duration"])
            workout.steps[i].target_power_w = _read_int(row["watt"])
            workout.steps[i].label = _read_str(row["label"])

    def register_sync() -> None:
        if sync_registry is not None:
            sync_registry["fn"] = sync_from_ui

    async def commit_fields() -> None:
        for row in fields:
            for key in ("duration", "watt", "label"):
                try:
                    await row[key].run_method("blur")
                except Exception:
                    pass

    def push_change() -> None:
        sync_from_ui()
        on_change()

    async def apply_change() -> None:
        await commit_fields()
        push_change()

    def rebuild() -> None:
        build_step_editor(workout, host, on_change, sync_registry)

    def add_step() -> None:
        sync_from_ui()
        last_w = workout.steps[-1].target_power_w if workout.steps else 150
        workout.steps.append(WorkoutStep(duration_s=60, target_power_w=last_w, label="Neu"))
        rebuild()
        on_change()

    with host:
        for index, step in enumerate(workout.steps):

            def remove_step(i: int = index) -> None:
                sync_from_ui()
                if len(workout.steps) > 1:
                    workout.steps.pop(i)
                    rebuild()
                    on_change()

            with ui.row().classes("w-full items-center gap-2"):
                ui.label(f"#{index + 1}").classes("w-8")
                duration = ui.number(
                    "Dauer (s)",
                    value=step.duration_s,
                    min=1,
                    max=7200,
                    step=5,
                    on_change=lambda _: push_change(),
                ).classes("w-32")
                watt = ui.number(
                    "Watt",
                    value=step.target_power_w,
                    min=0,
                    max=2000,
                    step=5,
                    on_change=lambda _: push_change(),
                ).classes("w-28")
                label = ui.input(
                    "Label",
                    value=step.label,
                    on_change=lambda _: push_change(),
                ).classes("flex-grow")
                fields.append({"duration": duration, "watt": watt, "label": label})

                ui.button(icon="delete", on_click=remove_step).props("flat dense")

        ui.button("Schritt hinzufuegen", on_click=add_step)
        ui.button("Aenderungen uebernehmen", on_click=apply_change).props("outline")

    register_sync()
    return sync_from_ui
