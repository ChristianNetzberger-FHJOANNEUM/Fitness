"""KICKR FTMS NiceGUI App — Einstiegspunkt."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from nicegui import background_tasks, ui

from app_kickr.connection import (
    connect_trainer,
    disconnect_trainer,
    scan_trainers,
    set_manual_erg,
    stop_trainer,
)
from app_kickr.fit_ui import show_fit_comparison
from app_kickr.keyboard_remote import KeyboardRemote
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
from core.fit import FitStore
from core.session import LiveSession, RecordingStore, SessionRecorder
from core.training import FreeTrainingController, FreeTrainingPhase
from core.workout import Workout, WorkoutRunner, WorkoutRunState, WorkoutStore, workout_from_free_session

DEFAULT_PORT = 8080


def run(port: int = DEFAULT_PORT) -> None:
    ensure_port_free(port)
    client = FtmsClient()
    session = LiveSession()
    recorder = SessionRecorder()
    recording_store = RecordingStore()
    fit_store = FitStore()
    workout_store = WorkoutStore()
    workout_runner = WorkoutRunner(client)
    free_controller = FreeTrainingController(client)

    latest_metrics = BikeMetrics()
    workout_ids = workout_store.list_ids()
    current_workout_id = workout_ids[0] if workout_ids else ""
    workout = workout_store.load(current_workout_id) if current_workout_id else Workout(name="Leer", steps=[])
    workout_task: asyncio.Task | None = None
    refs: dict = {}
    step_sync: dict = {"fn": lambda: None}
    last_chart_progress_s: float | None = None
    key_debug_lines: list[str] = []

    def refresh_free_ui() -> None:
        if not refs:
            return
        watts = free_controller.state.target_power_w
        refs["free_target_label"].set_text(str(watts))
        phase = free_controller.state.phase
        status_map = {
            FreeTrainingPhase.IDLE: "Bereit",
            FreeTrainingPhase.RUNNING: "Laeuft",
            FreeTrainingPhase.PAUSED: "Pause",
        }
        refs["free_status"].set_text(status_map.get(phase, str(phase)))
        if phase in (FreeTrainingPhase.RUNNING, FreeTrainingPhase.PAUSED):
            refs["free_elapsed_label"].set_text(f"Zeit: {session.elapsed_s:.0f} s")
        else:
            refs["free_elapsed_label"].set_text("")
        if phase == FreeTrainingPhase.RUNNING:
            refs["workout_target_label"].set_text(f"Frei: Ziel {watts} W")
        elif not workout_runner.state.running:
            refs["workout_target_label"].set_text("")
        pause_btn = refs.get("free_pause_btn")
        if pause_btn is not None:
            pause_btn.text = "Weiter" if phase == FreeTrainingPhase.PAUSED else "Pause"
            if phase == FreeTrainingPhase.IDLE:
                pause_btn.disable()
            else:
                pause_btn.enable()

    def log_key_debug(event, action: str = "") -> None:
        key = event.args.get("key", "?")
        code = event.args.get("code", "?")
        loc = event.args.get("location", 0)
        prefix = f"{action}: " if action else ""
        line = f"{prefix}{key} ({code}, loc={loc})"
        key_debug_lines.insert(0, line)
        del key_debug_lines[8:]
        if refs.get("free_key_debug") is not None:
            refs["free_key_debug"].set_text("\n".join(key_debug_lines))

    def on_key_test_changed(_event) -> None:
        enabled = bool(refs.get("free_key_test") and refs["free_key_test"].value)
        if refs.get("keyboard_remote") is not None:
            refs["keyboard_remote"].set_debug_mode(enabled)
        if enabled:
            key_debug_lines.clear()
            refs["free_key_debug"].set_text("Test aktiv — jede Taste wird hier angezeigt.")
        elif not key_debug_lines:
            refs["free_key_debug"].set_text("—")

    def _free_training_busy() -> bool:
        return free_controller.state.phase != FreeTrainingPhase.IDLE

    async def cancel_free_training() -> None:
        if free_controller.state.phase == FreeTrainingPhase.IDLE:
            return
        try:
            await free_controller.stop()
        except Exception:
            pass
        session.stop()
        if recorder.active and recorder.workout_id == "free_training":
            recorder.reset()
        refresh_free_ui()

    async def do_free_power_up() -> None:
        if not client.connected:
            ui.notify("Zuerst verbinden.", type="warning")
            return
        free_controller.state.step_w = int(refs["free_step"].value or 5)
        if free_controller.state.phase == FreeTrainingPhase.IDLE:
            free_controller.state.target_power_w = min(
                2000, free_controller.state.target_power_w + free_controller.state.step_w,
            )
            refs["target_power"].set_value(free_controller.state.target_power_w)
            refresh_free_ui()
            return
        if free_controller.state.phase != FreeTrainingPhase.RUNNING:
            return
        try:
            await free_controller.power_up()
            refresh_free_ui()
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")

    async def do_free_power_down() -> None:
        if not client.connected:
            ui.notify("Zuerst verbinden.", type="warning")
            return
        free_controller.state.step_w = int(refs["free_step"].value or 5)
        if free_controller.state.phase == FreeTrainingPhase.IDLE:
            free_controller.state.target_power_w = max(
                0, free_controller.state.target_power_w - free_controller.state.step_w,
            )
            refs["target_power"].set_value(free_controller.state.target_power_w)
            refresh_free_ui()
            return
        if free_controller.state.phase != FreeTrainingPhase.RUNNING:
            return
        try:
            await free_controller.power_down()
            refresh_free_ui()
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")

    async def do_free_transport() -> None:
        if not client.connected:
            return
        phase = free_controller.state.phase
        if phase == FreeTrainingPhase.RUNNING:
            await do_free_pause()
        elif phase == FreeTrainingPhase.PAUSED:
            await do_free_resume()
        else:
            await do_free_start()

    async def do_free_start() -> None:
        if not client.connected:
            ui.notify("Zuerst verbinden.", type="warning")
            return
        if workout_runner.state.running:
            ui.notify("Workout laeuft — zuerst stoppen.", type="warning")
            return
        refs["clap_monitor"].disarm()
        free_controller.state.step_w = int(refs["free_step"].value or 5)
        phase = free_controller.state.phase
        if phase == FreeTrainingPhase.IDLE:
            free_controller.state.target_power_w = int(refs["target_power"].value or 150)
            session.start(unlimited=True)
            refs["power_plot"].clear()
            refs["cadence_plot"].clear()
            recorder.start(
                workout_id="free_training",
                workout=Workout(name="Freies Training", steps=[]),
                trigger="free",
                trainer_name=client.device_name,
                trainer_address=refs["device_select"].value or "",
            )
        try:
            await free_controller.start()
            if phase == FreeTrainingPhase.PAUSED:
                session.resume()
                recorder.resume()
            set_status(f"Freies Training — Ziel {free_controller.state.target_power_w} W")
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")
        refresh_free_ui()

    async def do_free_pause() -> None:
        if free_controller.state.phase != FreeTrainingPhase.RUNNING:
            return
        try:
            await free_controller.pause()
            session.pause()
            recorder.pause()
            set_status("Freies Training pausiert")
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")
        refresh_free_ui()

    async def do_free_resume() -> None:
        if free_controller.state.phase != FreeTrainingPhase.PAUSED:
            return
        try:
            await free_controller.resume()
            session.resume()
            recorder.resume()
            set_status(f"Freies Training — Ziel {free_controller.state.target_power_w} W")
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")
        refresh_free_ui()

    async def do_free_pause_toggle() -> None:
        phase = free_controller.state.phase
        if phase == FreeTrainingPhase.RUNNING:
            await do_free_pause()
        elif phase == FreeTrainingPhase.PAUSED:
            await do_free_resume()

    async def do_free_stop() -> None:
        if free_controller.state.phase == FreeTrainingPhase.IDLE:
            return
        try:
            await free_controller.stop()
        except FtmsError as exc:
            ui.notify(str(exc), type="negative")
        session.stop()
        recorder.stop()
        refresh_free_ui()
        set_status("Freies Training beendet")
        if recorder.samples:
            free_save_dialog.open()
        else:
            recorder.reset()

    def discard_free_recording() -> None:
        recorder.reset()
        free_save_dialog.close()

    def save_free_recording_only() -> None:
        try:
            snapshot = Workout(name="Freies Training", steps=[])
            path = recording_store.save(recorder, snapshot)
            refs["last_recording_dir"] = str(path)
            ui.notify(f"Aufzeichnung gespeichert: {path.name}", type="positive")
        except Exception as exc:
            ui.notify(f"Speichern fehlgeschlagen: {exc}", type="warning")
        finally:
            recorder.reset()
            free_save_dialog.close()

    def open_free_as_workout() -> None:
        try:
            refs["pending_free_workout"] = workout_from_free_session(recorder.to_dict())
            free_save_dialog.close()
            free_workout_name.set_value(
                f"frei_{datetime.now().strftime('%Y%m%d_%H%M')}",
            )
            free_workout_dialog.open()
        except Exception as exc:
            ui.notify(f"Workout ableiten fehlgeschlagen: {exc}", type="negative")

    def confirm_free_workout_save() -> None:
        pending = refs.pop("pending_free_workout", None)
        if pending is None:
            free_workout_dialog.close()
            return
        slug = (free_workout_name.value or "").strip().replace(" ", "_")
        if not slug:
            ui.notify("Name eingeben.", type="warning")
            return
        pending.name = (free_workout_name.value or slug).strip()
        new_id = workout_store.save_user(pending, slug)
        try:
            path = recording_store.save(recorder, pending)
            refs["last_recording_dir"] = str(path)
            ui.notify(f"Gespeichert: Aufzeichnung + Workout user/{slug}", type="positive")
        except Exception as exc:
            ui.notify(f"Aufzeichnung nicht gespeichert: {exc}", type="warning")
        finally:
            recorder.reset()
        refs["workout_select"].set_options(workout_store.list_ids(), value=new_id)
        load_workout(new_id)
        free_workout_dialog.close()

    def set_status(msg: str) -> None:
        refs["status_label"].set_text(msg)

    def refresh_fit_select() -> None:
        labels = fit_store.list_labels()
        refs["fit_select"].set_options(labels)
        chosen = fit_store.find_for_workout(current_workout_id)
        if chosen is not None:
            refs["fit_select"].set_value(chosen.name)
        elif labels:
            refs["fit_select"].set_value(next(iter(labels)))

    def save_workout_recording() -> None:
        if not recorder.samples:
            recorder.reset()
            return
        try:
            path = recording_store.save(recorder, workout)
            refs["last_recording_dir"] = str(path)
            with with_alive_client(refs.get("workout_chart")):
                ui.notify(f"Aufzeichnung gespeichert: {path.name}", type="positive")
        except Exception as exc:
            with with_alive_client(refs.get("workout_chart")):
                ui.notify(f"Aufzeichnung nicht gespeichert: {exc}", type="warning")
        finally:
            recorder.reset()

    def do_fit_compare() -> None:
        filename = refs["fit_select"].value
        if not filename:
            ui.notify("Keine FIT-Datei in fit/ vorhanden.", type="warning")
            return
        fit_path = fit_store.path_for_name(filename)
        if fit_path is None:
            ui.notify("FIT-Datei nicht gefunden.", type="negative")
            return
        last_dir = refs.get("last_recording_dir")
        session_dir = None
        if last_dir:
            session_dir = Path(last_dir)
        elif current_workout_id:
            session_dir = recording_store.latest_for_workout(current_workout_id)
        try:
            lines = show_fit_comparison(
                refs["comparison_chart"], workout, fit_path, session_dir,
            )
            refs["fit_compare_status"].set_text("\n".join(lines))
        except Exception as exc:
            ui.notify(f"FIT-Vergleich fehlgeschlagen: {exc}", type="negative")

    def do_fit_archive() -> None:
        filename = refs["fit_select"].value
        if not filename:
            ui.notify("Keine FIT-Datei gewaehlt.", type="warning")
            return
        if not current_workout_id:
            ui.notify("Kein Workout geladen.", type="warning")
            return
        fit_path = fit_store.path_for_name(filename)
        if fit_path is None:
            ui.notify("FIT-Datei nicht gefunden.", type="negative")
            return
        if fit_path.parent.resolve() == fit_store.archive_dir.resolve():
            ui.notify("Datei liegt bereits im Archiv.", type="info")
            return
        try:
            dest = fit_store.archive(fit_path, current_workout_id)
            refresh_fit_select()
            refs["fit_select"].set_value(fit_store.label_for_path(dest))
            set_status(f"FIT archiviert: {dest.name}")
            ui.notify(f"Kopiert nach fit/archived/{dest.name}", type="positive")
        except Exception as exc:
            ui.notify(f"Archivieren fehlgeschlagen: {exc}", type="negative")

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
        refresh_fit_select()
        set_status(f"Workout geladen: {workout.name} ({workout.total_duration_s // 60} min)")

    def on_ble_metrics(metrics: BikeMetrics) -> None:
        nonlocal latest_metrics
        latest_metrics = metrics
        session.on_metrics(metrics)
        target_w: int | None = None
        if free_controller.state.phase == FreeTrainingPhase.RUNNING:
            target_w = free_controller.state.target_power_w
        elif workout_runner.state.running and workout_runner.state.current_step:
            target_w = workout_runner.state.current_step.target_power_w
        recorder.append(metrics, target_power_w=target_w)

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
        await cancel_free_training()
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

    async def launch_workout(*, sync_session: bool, trigger: str = "manual") -> None:
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
        if free_controller.state.phase != FreeTrainingPhase.IDLE:
            ui.notify("Freies Training aktiv — zuerst stoppen.", type="warning")
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

        recorder.start(
            workout_id=current_workout_id,
            workout=workout,
            trigger=trigger,
            trainer_name=client.device_name if client.connected else "",
            trainer_address=refs["device_select"].value or "",
        )

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
                save_workout_recording()
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
        await launch_workout(sync_session=False, trigger="manual")

    def do_arm_clap_start() -> None:
        step_sync["fn"]()
        if not client.connected:
            ui.notify("Zuerst verbinden.", type="warning")
            return
        if free_controller.state.phase != FreeTrainingPhase.IDLE:
            ui.notify("Freies Training aktiv — zuerst stoppen.", type="warning")
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
        await launch_workout(sync_session=True, trigger="clap")

    def on_clap_error(event) -> None:
        message = event.args.get("message", "Mikrofon-Fehler")
        refs["clap_status"].set_text(message)
        ui.notify(message, type="negative")

    def do_stop_workout() -> None:
        nonlocal last_chart_progress_s
        cancel_workout()
        save_workout_recording()
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
        if _free_training_busy():
            refresh_free_ui()
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
        do_free_start, do_free_pause_toggle, do_free_stop, do_free_power_up, do_free_power_down,
        do_start_workout, do_arm_clap_start, do_stop_clap_listen,
        do_stop_workout, do_save_workout, do_save_workout_as,
        on_workout_data_changed, load_workout,
        do_fit_compare, do_fit_archive, fit_store.list_labels(),
    ))
    def _on_kbd_power_up(event) -> None:
        log_key_debug(event, "Leistung +")
        background_tasks.create(do_free_power_up())

    def _on_kbd_power_down(event) -> None:
        log_key_debug(event, "Leistung −")
        background_tasks.create(do_free_power_down())

    def _on_kbd_transport(event) -> None:
        log_key_debug(event, "Start/Pause")
        background_tasks.create(do_free_transport())

    def _on_kbd_stop(event) -> None:
        log_key_debug(event, "Stop")
        background_tasks.create(do_free_stop())

    keyboard_remote = KeyboardRemote()
    keyboard_remote.on("power_up", _on_kbd_power_up)
    keyboard_remote.on("power_down", _on_kbd_power_down)
    keyboard_remote.on("transport", _on_kbd_transport)
    keyboard_remote.on("stop", _on_kbd_stop)
    keyboard_remote.on("key_debug", log_key_debug)
    refs["keyboard_remote"] = keyboard_remote
    refs["free_key_test"].on("update:model-value", on_key_test_changed)
    refs["clap_monitor"].on("clap", on_clap_detected)
    refs["clap_monitor"].on("error", on_clap_error)
    refs["workout_table"] = refresh_workout_summary(refs["workout_table_host"], workout)
    init_step_editor()
    refresh_fit_select()
    set_status("Bereit — KICKR einschalten, dann scannen.")

    with ui.dialog() as save_dialog, ui.card():
        ui.label("Workout speichern unter").classes("text-h6")
        save_as_name = ui.input("Dateiname (ohne .json)", value="mein_workout")
        with ui.row():
            ui.button("Abbrechen", on_click=save_dialog.close)
            ui.button("Speichern", on_click=confirm_save_as).props("color=primary")

    with ui.dialog() as free_save_dialog, ui.card():
        ui.label("Freies Training beendet").classes("text-h6")
        ui.label("Aufzeichnung speichern oder als Workout-Vorlage uebernehmen?").classes("text-body2")
        with ui.row().classes("q-gutter-sm"):
            ui.button("Verwerfen", on_click=discard_free_recording).props("flat")
            ui.button("Nur Aufzeichnung", on_click=save_free_recording_only).props("outline")
            ui.button("Als Workout …", on_click=open_free_as_workout).props("color=primary")

    with ui.dialog() as free_workout_dialog, ui.card():
        ui.label("Freies Training als Workout speichern").classes("text-h6")
        free_workout_name = ui.input("Workout-Name", value="frei_training")
        with ui.row():
            ui.button("Abbrechen", on_click=free_workout_dialog.close)
            ui.button("Speichern", on_click=confirm_free_workout_save).props("color=primary")

    refresh_free_ui()
    ui.timer(0.4, poll_live_ui)
    ui.run(title="KICKR FTMS", port=port, reload=False)
