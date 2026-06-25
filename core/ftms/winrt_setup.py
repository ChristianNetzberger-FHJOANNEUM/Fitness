"""Windows WinRT/COM fuer bleak vorbereiten (matplotlib/NiceGUI setzen sonst STA)."""

from __future__ import annotations

import sys


def prepare_winrt_for_bleak() -> None:
    """
    Vor BLE-Scan/Connect auf Windows aufrufen.

    ui.line_plot (matplotlib) initialisiert COM als STA. NiceGUI hat keine
    native Win32-Message-Loop — bleak braucht MTA oder uninitialize_sta().
    """
    if sys.platform != "win32":
        return
    try:
        from bleak.backends.winrt.util import uninitialize_sta

        uninitialize_sta()
    except ImportError:
        pass
