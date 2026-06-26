from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from core.workout.models import Workout

from .recorder import SessionRecorder


class RecordingStore:
    """Speichert KICKR-Aufzeichnungen unter recordings/."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "recordings"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slugify(workout_id: str) -> str:
        slug = workout_id.removeprefix("user/").replace("/", "_")
        return re.sub(r"[^\w\-]+", "_", slug)

    def session_dir_name(self, recorder: SessionRecorder) -> str:
        if recorder.recorded_at is None:
            raise ValueError("Recorder ohne Startzeit")
        ts = recorder.recorded_at.strftime("%Y-%m-%d_%H%M%S")
        return f"{ts}_{self._slugify(recorder.workout_id)}"

    def save(self, recorder: SessionRecorder, workout: Workout) -> Path:
        if not recorder.samples:
            raise ValueError("Keine Aufzeichnungsdaten")
        recorder.stop()
        session_dir = self.root / self.session_dir_name(recorder)
        session_dir.mkdir(parents=True, exist_ok=True)

        session_path = session_dir / "session.json"
        session_path.write_text(
            json.dumps(recorder.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        snapshot_path = session_dir / "workout_snapshot.json"
        snapshot_path.write_text(
            json.dumps(workout.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return session_dir

    def list_sessions(self) -> list[Path]:
        return sorted(
            (p for p in self.root.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )

    def latest_for_workout(self, workout_id: str) -> Path | None:
        slug = self._slugify(workout_id)
        for path in self.list_sessions():
            if path.name.endswith(f"_{slug}"):
                return path
        return None

    @staticmethod
    def load_session(path: Path) -> dict:
        return json.loads((path / "session.json").read_text(encoding="utf-8"))
