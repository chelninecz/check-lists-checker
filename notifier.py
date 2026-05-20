"""Windows toast notifications via winotify."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

APP_ID = "Check-List Checker"


def _icon_path() -> str | None:
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    p = base / "assets" / "icon.ico"
    return str(p) if p.exists() else None


def _build(title: str, msg: str):
    """Lazily import winotify so a missing dependency doesn't kill startup."""
    from winotify import Notification, audio  # noqa: WPS433

    kwargs = {"app_id": APP_ID, "title": title, "msg": msg}
    icon = _icon_path()
    if icon:
        kwargs["icon"] = icon
    toast = Notification(**kwargs)
    toast.set_audio(audio.Default, loop=False)
    return toast


def notify_new_file(file_path: str | Path) -> None:
    """Show a toast for a single newly detected file."""
    file_path = Path(file_path)
    try:
        toast = _build("Новый чек-лист", file_path.name)
        parent_uri = file_path.parent.as_uri()
        toast.add_actions(label="Открыть папку", launch=parent_uri)
        toast.show()
    except Exception:
        log.exception("Failed to show toast for %s", file_path)


def notify_overflow(folder_label: str, remaining: int) -> None:
    """Send a single 'and N more' toast when many files arrive at once."""
    try:
        toast = _build(f"Новые файлы — {folder_label}",
                       f"…и ещё {remaining} файлов")
        toast.show()
    except Exception:
        log.exception("Failed to show overflow toast")
