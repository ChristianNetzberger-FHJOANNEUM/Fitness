"""Freies ERG-Training (Start/Pause/Stop, Leistungsstufen)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.ftms.client import FtmsClient


class FreeTrainingPhase(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class FreeTrainingState:
    phase: FreeTrainingPhase = FreeTrainingPhase.IDLE
    target_power_w: int = 150
    step_w: int = 5


class FreeTrainingController:
    """Steuert manuelles ERG ohne festes Workout-Profil."""

    def __init__(
        self,
        client: FtmsClient,
        *,
        default_power_w: int = 150,
        step_w: int = 5,
    ) -> None:
        self._client = client
        self.state = FreeTrainingState(
            target_power_w=default_power_w,
            step_w=step_w,
        )

    @property
    def active(self) -> bool:
        return self.state.phase != FreeTrainingPhase.IDLE

    async def start(self) -> None:
        if self.state.phase == FreeTrainingPhase.RUNNING:
            return
        if self.state.phase == FreeTrainingPhase.PAUSED:
            await self.resume()
            return
        await self._client.apply_erg_power(self.state.target_power_w)
        self.state.phase = FreeTrainingPhase.RUNNING

    async def pause(self) -> None:
        if self.state.phase != FreeTrainingPhase.RUNNING:
            return
        await self._client.pause_trainer()
        self.state.phase = FreeTrainingPhase.PAUSED

    async def resume(self) -> None:
        if self.state.phase != FreeTrainingPhase.PAUSED:
            return
        await self._client.start()
        await self._client.set_target_power(self.state.target_power_w)
        self.state.phase = FreeTrainingPhase.RUNNING

    async def stop(self) -> None:
        if self.state.phase == FreeTrainingPhase.IDLE:
            return
        if self._client.connected:
            await self._client.stop()
        self.state.phase = FreeTrainingPhase.IDLE

    async def power_up(self) -> None:
        self.state.target_power_w = min(2000, self.state.target_power_w + self.state.step_w)
        if self.state.phase == FreeTrainingPhase.RUNNING:
            await self._client.set_target_power(self.state.target_power_w)

    async def power_down(self) -> None:
        self.state.target_power_w = max(0, self.state.target_power_w - self.state.step_w)
        if self.state.phase == FreeTrainingPhase.RUNNING:
            await self._client.set_target_power(self.state.target_power_w)

    async def apply_target(self) -> None:
        """Zielleistung am Trainer setzen (nur wenn Training laeuft)."""
        if self.state.phase == FreeTrainingPhase.RUNNING:
            await self._client.set_target_power(self.state.target_power_w)
