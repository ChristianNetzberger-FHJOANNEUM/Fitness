"""Windows WinRT/COM fuer bleak vorbereiten (matplotlib/NiceGUI setzen sonst STA)."""

from __future__ import annotations

import logging
import sys

_logger = logging.getLogger(__name__)


def prepare_winrt_for_bleak() -> None:
    """
    Direkt vor jedem BLE-Scan/Connect auf Windows aufrufen.

    ui.line_plot (matplotlib) initialisiert COM als STA. NiceGUI hat keine
    integrierte Win32-Message-Loop — bleak braucht MTA oder uninitialize_sta().

    Muss nach dem UI-Aufbau und unmittelbar vor bleak erfolgen (nicht beim
    App-Start, sonst setzt matplotlib danach wieder STA).
    """
    if sys.platform != "win32":
        return
    try:
        from bleak.backends.winrt.util import uninitialize_sta

        uninitialize_sta()
        _logger.debug("WinRT STA zurueckgesetzt vor BLE")
    except ImportError:
        pass
