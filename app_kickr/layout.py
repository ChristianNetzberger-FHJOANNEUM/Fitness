"""Haupt-UI Aufbau."""

from __future__ import annotations

from nicegui import ui

from app_kickr.clap_monitor import ClapMonitor
from core.workout import workout_chart_option


def build_ui(
    workout,
    workout_ids,
    current_workout_id,
    on_scan,
    on_connect,
    on_disconnect,
    on_set_erg,
    on_stop_trainer,
    on_start_workout,
    on_arm_clap_start,
    on_stop_clap_listen,
    on_stop_workout,
    on_save,
    on_save_as,
    on_workout_changed,
    load_workout,
):
    status_label = ui.label("Bereit").classes("text-caption")

    with ui.column().classes("w-full q-pa-md q-gutter-md"):
        with ui.row().classes("w-full q-gutter-md"):
            with ui.card().classes("w-72"):
                ui.label("Verbindung").classes("text-h6")
                scan_btn = ui.button("FTMS scannen", on_click=on_scan)
                device_select = ui.select({}, label="Trainer").classes("w-full")
                connect_btn = ui.button("Verbinden + Start", on_click=on_connect)
                ui.button("Trennen", on_click=on_disconnect)

            with ui.card().classes("w-48"):
                ui.label("Live").classes("text-h6")
                ui.label("Leistung (W)").classes("text-caption")
                power_label = ui.label("—").classes("text-h4")
                workout_target_label = ui.label("").classes("text-body2 text-primary")
                ui.label("Kadenz (rpm)").classes("text-caption")
                cadence_label = ui.label("—").classes("text-h4")

            with ui.card().classes("w-56"):
                ui.label("Manuell ERG").classes("text-h6")
                ui.label(
                    "Setzt Ziel-Leistung am KICKR. Du musst treten — ohne Tritt bleibt die Anzeige bei 0 W."
                ).classes("text-caption")
                target_power = ui.number("Zielleistung (W)", value=150, min=0, max=2000, step=5)
                ui.button("Setzen", on_click=on_set_erg)
                ui.button("Trainer Stop", on_click=on_stop_trainer)

        with ui.card().classes("w-full"):
            ui.label("Strip-Charts (Live)").classes("text-h6")
            power_plot = ui.line_plot(n=1, limit=400, figsize=(11, 2.2), close=False).classes("w-full")
            power_plot.with_legend(["Leistung (W)"])
            cadence_plot = ui.line_plot(n=1, limit=400, figsize=(11, 2.2), close=False).classes("w-full")
            cadence_plot.with_legend(["Kadenz (rpm)"])

        with ui.card().classes("w-full"):
            ui.label("Workout").classes("text-h6")
            workout_status = ui.label("Workout bereit").classes("text-body2")

            with ui.row().classes("w-full items-end q-gutter-md"):
                workout_select = ui.select(
                    workout_ids,
                    value=current_workout_id,
                    label="Workout",
                    on_change=lambda e: load_workout(e.value),
                ).classes("w-56")
                ui.button("Speichern", on_click=on_save)
                ui.button("Speichern unter …", on_click=on_save_as)
                ui.button("Workout starten", on_click=on_start_workout).props("color=primary")
                ui.button("Auf Klatschen warten", on_click=on_arm_clap_start).props("outline")
                ui.button("Workout stoppen", on_click=on_stop_workout)

            with ui.card().classes("w-full q-mt-sm"):
                ui.label("Synchroner Start (Fenix + PC)").classes("text-subtitle2")
                ui.label(
                    "Auf den Trainer steigen, Fenix-Aufzeichnung starten, dann klatschen oder rufen. "
                    "Der PC setzt die Strip-Charts auf t=0 und startet das Workout-ERG."
                ).classes("text-caption")
                with ui.row().classes("w-full items-center q-gutter-md"):
                    clap_threshold = ui.slider(min=0.04, max=0.35, step=0.01, value=0.12).classes("w-56")
                    ui.label("Empfindlichkeit").classes("text-caption")
                    ui.button("Warten abbrechen", on_click=on_stop_clap_listen).props("flat dense")
                clap_monitor = ClapMonitor()
                clap_status = ui.label("").classes("text-body2")

            workout_name_input = ui.input("Name", value=workout.name).classes("w-64")
            workout_name_input.on("change", lambda _: on_workout_changed())
            workout_desc_input = ui.input("Beschreibung", value=workout.description).classes("w-full")
            workout_desc_input.on("change", lambda _: on_workout_changed())

            ui.label("Profil-Vorschau (Graph)").classes("text-subtitle2 q-mt-sm")
            workout_chart = ui.echart(workout_chart_option(workout)).classes("w-full h-52")

            ui.label("Schritte (Tabelle) — wird bei Aenderungen unten aktualisiert").classes(
                "text-subtitle2 q-mt-sm"
            )
            workout_table_host = ui.column().classes("w-full")

            ui.label("Schritte bearbeiten").classes("text-subtitle2 q-mt-sm")
            step_editor_host = ui.column().classes("w-full")

    return {
        "status_label": status_label,
        "scan_btn": scan_btn,
        "connect_btn": connect_btn,
        "device_select": device_select,
        "power_label": power_label,
        "workout_target_label": workout_target_label,
        "cadence_label": cadence_label,
        "target_power": target_power,
        "power_plot": power_plot,
        "cadence_plot": cadence_plot,
        "workout_status": workout_status,
        "clap_threshold": clap_threshold,
        "clap_monitor": clap_monitor,
        "clap_status": clap_status,
        "workout_select": workout_select,
        "workout_name_input": workout_name_input,
        "workout_desc_input": workout_desc_input,
        "workout_chart": workout_chart,
        "workout_table_host": workout_table_host,
        "step_editor_host": step_editor_host,
    }
