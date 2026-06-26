"""CLI: python -m core.fit compare --workout grundlage_20min [--fit path] [--session path]"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.fit.compare import compare_profile_to_fit, compare_session_to_fit
from core.fit.parser import load_fit_activity
from core.fit.store import FitStore
from core.session.recording_store import RecordingStore
from core.workout import WorkoutStore


def main() -> None:
    parser = argparse.ArgumentParser(description="FIT mit Workout vergleichen")
    parser.add_argument("command", choices=["compare", "list"])
    parser.add_argument("--workout", default="grundlage_20min")
    parser.add_argument("--fit", type=Path, default=None)
    parser.add_argument("--session", type=Path, default=None, help="recordings/... Ordner oder session.json")
    args = parser.parse_args()

    if args.command == "list":
        for p in FitStore().list_paths():
            print(p.name)
        return

    workout = WorkoutStore().load(args.workout)
    fit_path = args.fit or FitStore().find_for_workout(args.workout)
    if fit_path is None:
        raise SystemExit(f"Keine FIT-Datei fuer {args.workout!r} in fit/")
    activity = load_fit_activity(fit_path)
    print(f"FIT: {fit_path.name} ({len(activity.samples)} Punkte, {activity.duration_s:.0f} s)")

    stats = compare_profile_to_fit(workout, activity)
    for line in stats.summary_lines():
        print(line)

    session_path = args.session
    if session_path is None:
        latest = RecordingStore().latest_for_workout(args.workout)
        if latest:
            session_path = latest / "session.json"
    if session_path:
        if session_path.is_dir():
            session_path = session_path / "session.json"
        if session_path.is_file():
            session = json.loads(session_path.read_text(encoding="utf-8"))
            print("---")
            for line in compare_session_to_fit(session, activity).summary_lines():
                print(line)


if __name__ == "__main__":
    main()
