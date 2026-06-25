from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkoutStep:
    duration_s: int
    target_power_w: int
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_s": self.duration_s,
            "target_power_w": self.target_power_w,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkoutStep:
        return cls(
            duration_s=int(data["duration_s"]),
            target_power_w=int(data["target_power_w"]),
            label=str(data.get("label", "")),
        )


@dataclass
class Workout:
    name: str
    steps: list[WorkoutStep] = field(default_factory=list)
    description: str = ""

    @property
    def total_duration_s(self) -> int:
        return sum(s.duration_s for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workout:
        return cls(
            name=str(data.get("name", "Workout")),
            description=str(data.get("description", "")),
            steps=[WorkoutStep.from_dict(s) for s in data.get("steps", [])],
        )
