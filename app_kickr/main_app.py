"""KICKR FTMS NiceGUI App — Einstiegspunkt."""

from __future__ import annotations

import asyncio

from nicegui import background_tasks, ui

from app_kickr.connection import (
    connect_trainer,
    disconnect_trainer,
    scan_trainers,
    set_manual_erg,
    stop_trainer,
)
from app_kickr.layout import build_ui
from app_kickr.port_free import ensure_port_free
from app_kickr.workout_ui import (
    build_step_editor,
    refresh_workout_chart,
    refresh_workout_summary,
    update_workout_progress_line,
)
from app_kickr.ui_safe import client_alive, with_alive_client
from core.ftms import BikeMetrics, FtmsClient
from core.ftms.client import FtmsError
from core.session import LiveSession
from core.workout import Workout, WorkoutRunner, WorkoutRunState, WorkoutStore

DEFAULT_PORT = 8080


def run(port: int = DEFAULT_PORT) -> None:
    ensure_port_free(port)
    client = FtmsClient()
    session = LiveSession()
    workout_store = WorkoutStore()
    workout_runner = WorkoutRunner(client)

    latest_metrics = BikeMetrics()
    workout_ids = workout_store.list_ids()
    current_workout_id = workout_ids[0] if workout_ids else ""
    workout = workout_store.load(current_workout_id) if current_workout_id else Workout(name="Leer", steps=[])
    workout_task: asyncio.Task | None = None
    refs: dict = {}
    step_sync: dict = {"fn": lambda: None}
    last_chart_progress_s: float | None = None

    def set_status(msg: str) -> None:
        refs["status_label"].set_text(msg)

    def refresh_live_labels(metrics: BikeMetrics) -> None:
        refs["power_label"].set_text(f"{metrics.power_w}" if metrics.power_w is not None else "—")
        refs["cadence_label"].set_text(
            f"{metrics.cadence_rpm:.0f}" if metrics.cadence_rpm is not None else "—"
        )

    def on_workout_data_changed() -> None:
        step_sync["fn"]()
        workout.name = refs["workout_name_input"].value or workout.name
        workout.description = refs["workout_desc_input"].value or ""
        progress = (
            workout_runner.state.total_elapsed_s if workout_runner.state.running else None
        )
        refresh_workout_chart(refs["workout_chart"], workout, progress_s=progress)
        refs["workout_table"] = refresh_workout_summary(refs["workout_table_host"], workout)

    def init_step_editor() -> None:
        build_step_editor(workout, refs["step_editor_host"], on_workout_data_changed, step_sync)

    def load_workout(workout_id: str) -> None:
        nonlocal workout, current_workout_id
        if not workout_id:
            return
        current_workout_id = workout_id
        workout = workout_store.load(workout_id)
        refs["clap_monitor"].disarm()
        refs["clap_status"].set_text("")
        refs["workout_name_input"].set_value(workout.name)
        refs["workout_desc_input"].set_value(workout.description)
        refresh_workout_chart(refs["workout_chart"], workout)
        refs["workout_table"] = refresh_workout_summary(refs["workout_table_host"], workout)
        init_step_editor()
        set_status(f"Workout geladen: {workout.name} ({workout.total_duration_s // 60} min)")

    def on_ble_metrics(metrics: BikeMetrics) -> None:
        nonlocal latest_metrics
        latest_metrics = metrics
        session.on_metrics(metrics)

    client.set_metrics_callback(on_ble_metrics)

    workout_runner.set_state_callback(lambda _state: None)

    def freeze_strip_charts() -> None:
        """Aufzeichnung stoppen, angezeigte Kurven behalten."""
        session.stop()

    def refresh_workout_progress_ui() -> None:
        nonlocal last_chart_progress_s
        if not client_alive(refs.get("workout_chart")):
            return
        state = workout_runner.state
        if state.running and state.current_step:
            step = state.current_step
            refs["workout_target_label"].set_text(f"Ziel: {step.target_power_w} W")
            erg_note = ""
            if client.target_power_w is not None and client.target_power_w != step.target_power_w:
                erg_note = f" (FTMS: {client.target_power_w} W)"
            refs["workout_status"].set_text(
                f"Schritt {state.step_index + 1}/{len(workout.steps)}: "
                f"{step.label} — {step.target_power_w} W{erg_note} "
                f"({state.step_elapsed_s:.0f}/{step.duration_s} s)"
            )
            progress = state.total_elapsed_s
            if (
                last_chart_progress_s is None
                or abs(progress - last_chart_progress_s) >= 2.0
            ):
                update_workout_progress_line(refs["workout_chart"], workout, progress)
                last_chart_progress_s = progress
        elif last_chart_progress_s is not None:
            last_chart_progress_s = None

    def cancel_workout() -> None:
        nonlocal workout_task
        workout_runner.cancel()
        if workout_task is not None:
            workout_task.cancel()
            workout_task = None

    async def do_scan() -> None:
        refs["scan_btn"].disable()
        set_status("Scanne nach FTMS-Geraeten …")
        try:
            _, options = await scan_trainers(client, set_status)
            refs["device_select"].set_options(options, value=options and next(iter(options)))
            set_status(f"{len(options)} Geraet(e) gefunden.")
        except Exception as exc:
            set_status(f"Scan fehlgeschlagen: {exc}")
        finally:
            refs["scan_btn"].enable()

    async def do_connect() -> None:
        address = refs["device_select"].value
        if not address:
            ui.notify("Bitte zuerst scannen.", type="warning")
            return
        refs["connect_btn"].disable()
        set_status(f"Verbinde mit {address} …")
        try:
            await connect_trainer(
                client, session, address,
                refs["power_plot"], refs["cadence_plot"],
                set_status, refresh_live_labels,
            )
        except FtmsError as exc:
            set_status(str(exc))
            ui.notify(str(exc), type="negative")
        except Exception as exc:
            set_status(f"Verbindung fehlgeschlagen: {exc}")
            ui.notify(str(exc), type="negative")
        finally:
            refs["connect_btn"].enable()

    async def do_disconnect() -> None:
        await disconnect_trainer(
            client, session, refs["power_plot"], refs["cadence_plot"],
            refresh_live_labels, set_status, cancel_workout,
        )

    async def do_set_erg() -> None:
        try:
            await set_manual_erg(client, int(refs["target_power"].value or 0), set_status)
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")

    async def do_stop_trainer() -> None:
        try:
            await stop_trainer(client, set_status)
        except Exception as exc:
            ui.notify(str(exc), type="negative")

    async def launch_workout(*, sync_session: bool) -> None:
        nonlocal workout_task, last_chart_progress_s
        step_sync["fn"]()
        last_chart_progress_s = None
        refresh_workout_chart(
            refs["workout_chart"], workout, progress_s=None, full_replace=True,
        )
        refs["workout_table"] = refresh_workout_summary(refs["workout_table_host"], workout)
        if not client.connected:
            ui.notify("Zuerst verbinden.", type="warning")
            return
        if workout_runner.state.running or not workout.steps:
            ui.notify("Workout laeuft bereits oder ist leer.", type="warning")
            return

        if sync_session:
            session.reset()
            session.start()
            refs["power_plot"].clear()
            refs["cadence_plot"].clear()
        elif not session.active:
            session.start()

        first_w = workout.steps[0].target_power_w

        async def _run() -> None:
            try:
                await workout_runner.run(workout)
                with with_alive_client(refs.get("workout_chart")):
                    ui.notify("Workout beendet.", type="positive")
            except Exception as exc:
                with with_alive_client(refs.get("workout_chart")):
                    set_status(f"Workout-Fehler: {exc}")
                    ui.notify(f"Workout abgebrochen: {exc}", type="negative")
            finally:
                freeze_strip_charts()
                with with_alive_client(refs.get("workout_chart")):
                    refs["workout_target_label"].set_text("")
                    refresh_workout_chart(
                        refs["workout_chart"], workout, progress_s=None, full_replace=True,
                    )
                    last_chart_progress_s = None
                    if not workout_runner.state.running:
                        refs["workout_status"].set_text("Workout bereit")

        workout_task = background_tasks.create(_run(), name="workout-run")
        set_status(f"Workout laeuft — Ziel Schritt 1: {first_w} W")
        ui.notify(f"Workout gestartet — ERG Ziel: {first_w} W", type="positive")

    async def do_start_workout() -> None:
        await launch_workout(sync_session=False)

    def do_arm_clap_start() -> None:
        step_sync["fn"]()
        if not client.connected:
            ui.notify("Zuerst verbinden.", type="warning")
            return
        if workout_runner.state.running or not workout.steps:
            ui.notify("Workout laeuft bereits oder ist leer.", type="warning")
            return
        threshold = float(refs["clap_threshold"].value or 0.12)
        refs["clap_status"].set_text(
            "Bereit — Fenix starten, auf den Trainer steigen, dann klatschen oder rufen."
        )
        refs["clap_monitor"].arm(threshold)
        ui.notify("Warte auf Klatschen … (Mikrofon-Zugriff erlauben)", type="info")

    def do_stop_clap_listen() -> None:
        refs["clap_monitor"].disarm()
        refs["clap_status"].set_text("Warten abgebrochen.")

    async def on_clap_detected(_event) -> None:
        refs["clap_status"].set_text("Klatschen erkannt — Workout startet!")
        await launch_workout(sync_session=True)

    def on_clap_error(event) -> None:
        message = event.args.get("message", "Mikrofon-Fehler")
        refs["clap_status"].set_text(message)
        ui.notify(message, type="negative")

    def do_stop_workout() -> None:
        nonlocal last_chart_progress_s
        cancel_workout()
        freeze_strip_charts()
        refs["clap_monitor"].disarm()
        refs["clap_status"].set_text("")
        refs["workout_target_label"].set_text("")
        last_chart_progress_s = None
        refresh_workout_chart(refs["workout_chart"], workout, progress_s=None, full_replace=True)
        refs["workout_status"].set_text("Workout gestoppt")

    def do_save_workout() -> None:
        if not current_workout_id:
            return
        on_workout_data_changed()
        workout_store.save(workout, current_workout_id)
        refs["workout_select"].set_options(workout_store.list_ids(), value=current_workout_id)
        msg = f"Gespeichert: {current_workout_id}"
        if not current_workout_id.startswith("user/"):
            msg += " (Vorlage ueberschrieben — Kopien besser mit «Speichern unter …»)"
        ui.notify(msg, type="positive")

    def do_save_workout_as() -> None:
        save_dialog.open()

    def confirm_save_as() -> None:
        slug = (save_as_name.value or "").strip().replace(" ", "_")
        if not slug:
            ui.notify("Name eingeben.", type="warning")
            return
        on_workout_data_changed()
        new_id = workout_store.save_user(workout, slug)
        refs["workout_select"].set_options(workout_store.list_ids(), value=new_id)
        load_workout(new_id)
        save_dialog.close()
        ui.notify(f"Gespeichert: user/{slug}", type="positive")

    def poll_live_ui() -> None:
        if not client_alive(refs.get("power_label")):
            return
        refresh_live_labels(latest_metrics)
        refresh_workout_progress_ui()
        drained = session.drain_for_plot()
        if drained is None:
            return
        times, power, cadence = drained
        if times and client_alive(refs.get("power_plot")):
            refs["power_plot"].push(times, [power], x_limits="auto", y_limits="auto")
            refs["cadence_plot"].push(times, [cadence], x_limits="auto", y_limits="auto")

    ui.page_title("KICKR FTMS")
    with ui.header().classes("items-center justify-between"):
        ui.label("KICKR FTMS Labor").classes("text-h5")

    refs.update(build_ui(
        workout, workout_ids, current_workout_id,
        do_scan, do_connect, do_disconnect, do_set_erg, do_stop_trainer,
        do_start_workout, do_arm_clap_start, do_stop_clap_listen,
        do_stop_workout, do_save_workout, do_save_workout_as,
        on_workout_data_changed, load_workout,
    ))
    refs["clap_monitor"].on("clap", on_clap_detected)
    refs["clap_monitor"].on("error", on_clap_error)
    refs["workout_table"] = refresh_workout_summary(refs["workout_table_host"], workout)
    init_step_editor()
    set_status("Bereit — KICKR einschalten, dann scannen.")

    with ui.dialog() as save_dialog, ui.card():
        ui.label("Workout speichern unter").classes("text-h6")
        save_as_name = ui.input("Dateiname (ohne .json)", value="mein_workout")
        with ui.row():
            ui.button("Abbrechen", on_click=save_dialog.close)
            ui.button("Speichern", on_click=confirm_save_as).props("color=primary")

    ui.timer(0.4, poll_live_ui)
    ui.run(title="KICKR FTMS", port=port, reload=False)
