from __future__ import annotations

from pathlib import Path

from .archive import archive_fit_copy


class FitStore:
    """FIT-Dateien im Ordner fit/ (beliebige Dateinamen)."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "fit"
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def archive_dir(self) -> Path:
        return self.root / "archived"

    def list_paths(self) -> list[Path]:
        root_files = sorted(self.root.glob("*.fit"), key=lambda p: p.name.lower())
        archived = sorted(self.archive_dir.glob("*.fit"), key=lambda p: p.name.lower())
        return root_files + archived

    def label_for_path(self, path: Path) -> str:
        if path.parent.resolve() == self.archive_dir.resolve():
            return f"archived/{path.name}"
        return path.name

    def list_labels(self) -> dict[str, str]:
        return {self.label_for_path(p): self.label_for_path(p) for p in self.list_paths()}

    def find_for_workout(self, workout_id: str) -> Path | None:
        """Datei, deren Name den Workout-Slug enthaelt (z. B. grundlage_20min.fit)."""
        slug = workout_id.removeprefix("user/").replace("/", "_").lower()
        for path in self.list_paths():
            if slug in path.stem.lower():
                return path
        return None

    def path_for_name(self, filename: str) -> Path | None:
        if filename.startswith("archived/"):
            path = self.archive_dir / filename.removeprefix("archived/")
        else:
            path = self.root / filename
        return path if path.is_file() else None

    def archive(self, source: Path, workout_id: str) -> Path:
        """Kopiert FIT mit Datums-Prefix nach fit/archived/."""
        return archive_fit_copy(source, self.archive_dir, workout_id)
