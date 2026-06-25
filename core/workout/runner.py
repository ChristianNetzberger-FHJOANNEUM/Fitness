from __future__ import annotations

import asyncio
from typing import Callable

from core.ftms.client import FtmsClient

from .models import Workout, WorkoutStep


class WorkoutRunState:
    def __init__(self) -> None:
        self.running: bool = False
        self.step_index: int = 0
        self.step_elapsed_s: float = 0.0
        self.total_elapsed_s: float = 0.0
        self.current_step: WorkoutStep | None = None
        self.applied_power_w: int | None = None


class WorkoutRunner:
    """Fuehrt ein Intervall-Workout per ERG auf dem FTMS-Client aus."""

    def __init__(self, client: FtmsClient) -> None:
        self._client = client
        self._cancelled = False
        self._state = WorkoutRunState()
        self._on_state: Callable[[WorkoutRunState], None] | None = None

    @property
    def state(self) -> WorkoutRunState:
        return self._state

    def set_state_callback(self, callback: Callable[[WorkoutRunState], None] | None) -> None:
        self._on_state = callback

    def cancel(self) -> None:
        self._cancelled = True

    def _notify(self) -> None:
        if self._on_state is not None:
            self._on_state(self._state)

    async def run(self, workout: Workout) -> None:
        if not self._client.connected:
            raise RuntimeError("Trainer nicht verbunden")
        if not workout.steps:
            raise RuntimeError("Workout hat keine Schritte")

        self._cancelled = False
        self._state = WorkoutRunState()
        self._state.running = True
        self._notify()

        tick = 0.25
        try:
            for index, step in enumerate(workout.steps):
                if self._cancelled:
                    break

                self._state.step_index = index
                self._state.current_step = step
                self._state.step_elapsed_s = 0.0
                self._notify()

                await self._client.apply_erg_power(step.target_power_w)
                self._state.applied_power_w = step.target_power_w
                self._notify()

                elapsed_in_step = 0.0
                while elapsed_in_step < step.duration_s and not self._cancelled:
                    await asyncio.sleep(tick)
                    elapsed_in_step = min(step.duration_s, elapsed_in_step + tick)
                    self._state.step_elapsed_s = elapsed_in_step
                    self._state.total_elapsed_s = (
                        sum(s.duration_s for s in workout.steps[:index]) + elapsed_in_step
                    )
                    self._notify()
        finally:
            self._state.running = False
            self._state.current_step = None
            self._notify()
