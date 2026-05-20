"""System tray icon and its context menu, powered by pystray."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image

log = logging.getLogger(__name__)


def _load_icon_image() -> Image.Image:
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    path = base / "assets" / "icon.ico"
    if path.exists():
        try:
            return Image.open(path)
        except Exception:
            log.exception("Failed to load %s, falling back to placeholder", path)
    img = Image.new("RGB", (64, 64), color=(30, 120, 200))
    return img


class TrayIcon:
    def __init__(
        self,
        on_show: Callable[[], None],
        on_scan_now: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_show = on_show
        self._on_scan_now = on_scan_now
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Показать", self._safe(self._on_show), default=True),
            pystray.MenuItem("Сканировать сейчас", self._safe(self._on_scan_now)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._safe(self._on_quit)),
        )

    @staticmethod
    def _safe(fn: Callable[[], None]):
        def wrapped(icon=None, item=None) -> None:
            try:
                fn()
            except Exception:
                log.exception("Tray menu handler crashed")
        return wrapped

    def start(self) -> None:
        image = _load_icon_image()
        self._icon = pystray.Icon(
            "check-list-checker",
            image,
            "Check-List Checker",
            self._menu(),
        )
        self._thread = threading.Thread(
            target=self._icon.run, name="pystray", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                log.exception("Failed to stop tray icon")
            self._icon = None
