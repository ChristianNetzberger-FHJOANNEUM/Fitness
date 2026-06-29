"""Hilfen fuer sichere NiceGUI-Updates (kein Zugriff auf geloeschte Clients)."""

from __future__ import annotations

import logging

from nicegui import Client, ui
from nicegui.element import Element

_logger = logging.getLogger(__name__)


def client_alive(element: Element | None) -> bool:
    if element is None or element.is_deleted:
        return False
    try:
        return element.client.id in Client.instances
    except Exception:
        return False


def safe_notify(message: str, *, type: str = "info", timeout: int | None = None) -> None:
    try:
        if timeout is None:
            ui.notify(message, type=type)
        else:
            ui.notify(message, type=type, timeout=timeout)
    except Exception:
        _logger.warning("ui.notify fehlgeschlagen: %s", message, exc_info=True)


def with_alive_client(element: Element | None):
    """Context manager: nur wenn Browser-Client noch verbunden ist."""
    if client_alive(element):
        return element.client
    return _NullContext()


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False
