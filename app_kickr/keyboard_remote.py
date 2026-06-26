"""Tastatur- und Fernbedienungs-Shortcuts fuer freies Training."""

from __future__ import annotations

from typing import Callable

from nicegui import events
from nicegui.element import Element


class KeyboardRemote(Element, component="keyboard_remote.js"):

    def __init__(
        self,
        *,
        on_power_up: Callable[[events.GenericEventArguments], None] | None = None,
        on_power_down: Callable[[events.GenericEventArguments], None] | None = None,
        on_transport: Callable[[events.GenericEventArguments], None] | None = None,
        on_stop: Callable[[events.GenericEventArguments], None] | None = None,
    ) -> None:
        super().__init__()
        if on_power_up is not None:
            self.on("power_up", on_power_up)
        if on_power_down is not None:
            self.on("power_down", on_power_down)
        if on_transport is not None:
            self.on("transport", on_transport)
        if on_stop is not None:
            self.on("stop", on_stop)

    def enable(self) -> None:
        self.run_method("enable")

    def set_debug_mode(self, enabled: bool) -> None:
        self.run_method("set_debug_mode", enabled)
