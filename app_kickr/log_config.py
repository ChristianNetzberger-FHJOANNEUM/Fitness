"""Zentrales Logging fuer NiceGUI-Timer und BLE-Hintergrundtasks."""

from __future__ import annotations

import asyncio
import faulthandler
import logging
import sys

logger = logging.getLogger("app_kickr")


def setup_logging(*, bleak_debug: bool = False) -> None:
    faulthandler.enable(file=sys.stderr, all_threads=True)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
    logging.getLogger("bleak").setLevel(logging.DEBUG if bleak_debug else logging.WARNING)


def install_asyncio_exception_handler() -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    previous = loop.get_exception_handler()

    def handler(inner_loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        message = context.get("message", "asyncio")
        if exc is not None:
            logger.error("Asyncio: %s", message, exc_info=exc)
        else:
            logger.error("Asyncio: %s — %s", message, context)
        if previous is not None:
            previous(inner_loop, context)

    loop.set_exception_handler(handler)
