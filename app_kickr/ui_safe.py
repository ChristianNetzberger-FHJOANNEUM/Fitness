"""Hilfen fuer sichere NiceGUI-Updates (kein Zugriff auf geloeschte Clients)."""

from __future__ import annotations

from nicegui import Client
from nicegui.element import Element


def client_alive(element: Element | None) -> bool:
    if element is None or element.is_deleted:
        return False
    try:
        return element.client.id in Client.instances
    except Exception:
        return False


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
