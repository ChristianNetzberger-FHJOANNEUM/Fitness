from __future__ import annotations

import json
from pathlib import Path

from .models import Workout


class WorkoutStore:
    """Laedt und speichert Workouts als JSON unter workouts/."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "workouts"
        self.user_dir = self.root / "user"
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def list_ids(self) -> list[str]:
        ids: list[str] = []
        for path in sorted(self.root.glob("*.json")):
            ids.append(path.stem)
        for path in sorted(self.user_dir.glob("*.json")):
            ids.append(f"user/{path.stem}")
        return ids

    def path_for(self, workout_id: str) -> Path:
        if workout_id.startswith("user/"):
            return self.user_dir / f"{workout_id.removeprefix('user/')}.json"
        return self.root / f"{workout_id}.json"

    def load(self, workout_id: str) -> Workout:
        path = self.path_for(workout_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Workout.from_dict(data)

    def save(self, workout: Workout, workout_id: str) -> Path:
        path = self.path_for(workout_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(workout.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def save_user(self, workout: Workout, slug: str) -> str:
        workout_id = f"user/{slug}"
        self.save(workout, workout_id)
        return workout_id
