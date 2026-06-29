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
    on_scan_hr,
    on_connect_hr,
    on_disconnect_hr,
    on_set_erg,
    on_stop_trainer,
    on_free_start,
    on_free_pause_toggle,
    on_free_stop,
    on_free_power_up,
    on_free_power_down,
    on_start_workout,
    on_arm_clap_start,
    on_stop_clap_listen,
    on_stop_workout,
    on_save,
    on_save_as,
    on_workout_changed,
    load_workout,
    on_fit_compare,
    on_fit_archive,
    fit_files,
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

            with ui.card().classes("w-64"):
                ui.label("Herzfrequenz").classes("text-h6")
                ui.label("BLE-Brustgurt (z. B. Polar H10)").classes("text-caption")
                scan_hr_btn = ui.button("HF scannen", on_click=on_scan_hr).props("dense")
                hr_select = ui.select({}, label="HF-Sensor").classes("w-full")
                with ui.row().classes("q-gutter-sm"):
                    connect_hr_btn = ui.button("Verbinden", on_click=on_connect_hr).props("dense")
                    ui.button("Trennen", on_click=on_disconnect_hr).props("dense flat")
                ui.label("HF (bpm)").classes("text-caption q-mt-xs")
                hr_label = ui.label("—").classes("text-h4")
                hr_contact_label = ui.label("").classes("text-caption")

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
            power_plot = ui.line_plot(n=1, limit=1200, figsize=(11, 2.2), close=False).classes("w-full")
            power_plot.with_legend(["Leistung (W)"])
            cadence_plot = ui.line_plot(n=1, limit=1200, figsize=(11, 2.2), close=False).classes("w-full")
            cadence_plot.with_legend(["Kadenz (rpm)"])
            hr_plot = ui.line_plot(n=1, limit=1200, figsize=(11, 2.2), close=False).classes("w-full")
            hr_plot.with_legend(["HF (bpm)"])

        with ui.expansion("Freies Training", icon="directions_bike").classes("w-full shadow-1"):
            with ui.row().classes("w-full items-start q-col-gutter-md no-wrap"):
                with ui.column().classes("col-grow"):
                    with ui.row().classes("w-full items-center q-gutter-lg"):
                        with ui.column().classes("items-center"):
                            ui.label("Ziel").classes("text-caption")
                            free_target_label = ui.label("150").classes("text-h3 text-primary")
                            ui.label("Watt").classes("text-caption")
                        with ui.column():
                            free_status = ui.label("Bereit").classes("text-body1")
                        free_step = ui.number("Stufe (W)", value=5, min=1, max=50, step=1).classes("w-28")
                    with ui.row().classes("w-full items-center q-gutter-md q-mt-sm"):
                        ui.button("Start", on_click=on_free_start).props("color=primary")
                        free_pause_btn = ui.button("Pause", on_click=on_free_pause_toggle).props("outline")
                        ui.button("Stop", on_click=on_free_stop).props("outline color=negative")
                        ui.button("▼", on_click=on_free_power_down).props("outline dense").classes("text-h6")
                        ui.button("▲", on_click=on_free_power_up).props("outline dense").classes("text-h6")
                with ui.column().classes("items-center q-px-sm shrink-0"):
                    ui.label("Zeit").classes("text-caption")
                    free_time_clock = ui.label("00:00:00").classes("text-weight-bold").style(
                        "font-size: 2.75rem; line-height: 1.1; font-family: ui-monospace, monospace; "
                        "font-variant-numeric: tabular-nums; letter-spacing: 0.04em;"
                    )
                with ui.column().classes("w-72 shrink-0"):
                    ui.label("Tasten / Fernbedienung").classes("text-subtitle2")
                    ui.label(
                        "Logitech-Remote:\n"
                        "PageUp / PageDown — Leistung + / −\n"
                        ". (Punkt) — Stop\n"
                        "Start-Taste — F5 oder Esc (wechselnd)\n"
                        "  → Start / Pause / Weiter\n"
                        "Enter — Start / Pause (PC-Tastatur)"
                    ).classes("text-caption whitespace-pre-line")
                    free_key_test = ui.switch("Tasten testen (keine Steuerung)")
                    free_key_debug = ui.label("—").classes(
                        "text-caption text-grey-8 whitespace-pre-line q-mt-xs"
                    )

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

            ui.label("Fenix FIT Vergleich").classes("text-subtitle2 q-mt-md")
            ui.label(
                "FIT-Dateien nach fit/ kopieren (z. B. grundlage_20min.fit oder Garmin-Export). "
                "«Archivieren» kopiert die gewaehlte Datei nach fit/archived/ mit Datum und Workout im Namen. "
                "Ohne KICKR-Aufzeichnung: Profil vs FIT. Mit Aufzeichnung: zusaetzlich KICKR vs FIT."
            ).classes("text-caption")
            with ui.row().classes("w-full items-end q-gutter-md"):
                fit_default = next(iter(fit_files), None) if fit_files else None
                fit_select = ui.select(
                    fit_files or {},
                    value=fit_default,
                    label="FIT-Datei",
                ).classes("w-80")
                ui.button("Vergleichen", on_click=lambda: on_fit_compare()).props("outline")
                ui.button("Archivieren", on_click=lambda: on_fit_archive()).props("outline")
            fit_compare_status = ui.label("").classes("text-body2")
            comparison_chart = ui.echart({"title": {"text": "FIT-Vergleich"}}).classes("w-full h-56")

    return {
        "status_label": status_label,
        "scan_btn": scan_btn,
        "connect_btn": connect_btn,
        "device_select": device_select,
        "scan_hr_btn": scan_hr_btn,
        "connect_hr_btn": connect_hr_btn,
        "hr_select": hr_select,
        "hr_label": hr_label,
        "hr_contact_label": hr_contact_label,
        "power_label": power_label,
        "workout_target_label": workout_target_label,
        "cadence_label": cadence_label,
        "target_power": target_power,
        "power_plot": power_plot,
        "cadence_plot": cadence_plot,
        "hr_plot": hr_plot,
        "free_target_label": free_target_label,
        "free_status": free_status,
        "free_time_clock": free_time_clock,
        "free_step": free_step,
        "free_pause_btn": free_pause_btn,
        "free_key_test": free_key_test,
        "free_key_debug": free_key_debug,
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
        "fit_select": fit_select,
        "fit_compare_status": fit_compare_status,
        "comparison_chart": comparison_chart,
    }
