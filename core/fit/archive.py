"""FIT-Dateien mit Aufzeichnungsdatum im Namen nach fit/archived/ kopieren."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from fitparse import FitFile

from .parser import load_fit_activity


def read_local_start_time(fit_path: Path) -> datetime:
    """Lokale Startzeit aus FIT-Metadaten (activity.local_timestamp oder session.start_time)."""
    fit_file = FitFile(str(fit_path))
    for msg in fit_file.get_messages("activity"):
        local = msg.get_value("local_timestamp")
        if local is not None:
            return local

    activity = load_fit_activity(fit_path)
    if activity.start_time is not None:
        return activity.start_time.astimezone()
    raise ValueError(f"Kein Startzeitpunkt in {fit_path.name}")


def dated_fit_basename(start: datetime, workout_id: str) -> str:
    slug = workout_id.removeprefix("user/").replace("/", "_").lower()
    return f"{start.strftime('%Y-%m-%d_%H%M%S')}_{slug}"


def archive_fit_copy(source: Path, archive_dir: Path, workout_id: str) -> Path:
    """Kopiert FIT nach archive_dir mit Datum + Workout-Slug im Dateinamen."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    start = read_local_start_time(source)
    base = dated_fit_basename(start, workout_id)
    dest = archive_dir / f"{base}.fit"
    if dest.exists():
        for i in range(2, 100):
            candidate = archive_dir / f"{base}_{i}.fit"
            if not candidate.exists():
                dest = candidate
                break
    shutil.copy2(source, dest)
    return dest
