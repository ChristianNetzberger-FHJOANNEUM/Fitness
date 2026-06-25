"""Browser-Mikrofon: Klatschen/Rufen zum synchronen Workout-Start."""

from __future__ import annotations

from typing import Callable

from nicegui import events
from nicegui.element import Element


class ClapMonitor(Element, component="clap_monitor.js"):

    def __init__(
        self,
        *,
        on_clap: Callable[[events.GenericEventArguments], None] | None = None,
        on_error: Callable[[events.GenericEventArguments], None] | None = None,
    ) -> None:
        super().__init__()
        if on_clap is not None:
            self.on("clap", on_clap)
        if on_error is not None:
            self.on("error", on_error)

    def arm(self, threshold: float = 0.12) -> None:
        self.run_method("arm", threshold)

    def disarm(self) -> None:
        self.run_method("disarm")
