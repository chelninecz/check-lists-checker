"""Windows toast notifications via windows-toasts (WinRT).

We use ``InteractableWindowsToaster`` so we can attach a real Python
callback to the "Открыть папку" button. For Windows to route the
activation back to our process, we register an AppUserModelID in HKCU.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import winreg
from pathlib import Path
from threading import Lock

from state import app_data_dir

log = logging.getLogger(__name__)

APP_NAME = "Check-List Checker"
# Reverse-DNS-ish identifier. Must match the AUMID we register in HKCU.
AUMID = "ChecklistChecker.App"

_setup_done = False
_setup_lock = Lock()
_toaster = None  # type: ignore[var-annotated]


def _bundled_icon_path() -> Path | None:
    """Path to icon.ico inside the running bundle (dev tree or PyInstaller)."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    p = base / "assets" / "icon.ico"
    return p if p.exists() else None


def _persistent_icon_path() -> Path | None:
    """Copy the bundled icon into %APPDATA% (once) and return the stable path.

    Required for the AUMID registry entry: under PyInstaller, ``_MEIPASS``
    points at a temporary directory that disappears on exit, so a registry
    value referencing it would dangle the next time the user clicks a toast.
    """
    src = _bundled_icon_path()
    if src is None:
        return None
    dest = app_data_dir() / "icon.ico"
    try:
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
        return dest
    except OSError:
        log.exception("Failed to copy icon to %s", dest)
        return src  # fall back to the bundled path


def _register_aumid() -> None:
    """Register the AppUserModelID under HKCU so Windows knows which
    application a toast activation should be routed to. Cheap, per-user,
    idempotent."""
    icon = _persistent_icon_path()
    try:
        key_path = rf"Software\Classes\AppUserModelId\{AUMID}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            if icon is not None:
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, str(icon))
                # Light gray background tile in Action Center.
                winreg.SetValueEx(k, "IconBackgroundColor", 0,
                                  winreg.REG_SZ, "FFDDDDDD")
    except OSError:
        log.exception("Failed to register AUMID %s", AUMID)


def _ensure_setup() -> None:
    global _setup_done, _toaster
    with _setup_lock:
        if _setup_done:
            return
        _register_aumid()
        try:
            from windows_toasts import InteractableWindowsToaster
            _toaster = InteractableWindowsToaster(APP_NAME, AUMID)
        except Exception:
            log.exception("Failed to create InteractableWindowsToaster")
            _toaster = None
        _setup_done = True


def _open_in_explorer(target: str) -> None:
    if not target:
        return
    try:
        p = Path(target)
        if p.is_dir():
            # Pass a raw command line — explorer.exe is picky about quoting.
            subprocess.Popen(f'explorer "{target}"')
        else:
            subprocess.Popen(f'explorer /select,"{target}"')
    except Exception:
        log.exception("Failed to open explorer for %s", target)


def _on_activated(event) -> None:
    arg = getattr(event, "arguments", None)
    log.info("Toast activated, arguments=%r", arg)
    if arg:
        _open_in_explorer(arg)


def notify_new_file(file_path: str | Path) -> None:
    """Show a toast with an 'Открыть папку' button that actually works."""
    file_path = Path(file_path)
    _ensure_setup()
    if _toaster is None:
        return
    try:
        from windows_toasts import (
            Toast,
            ToastButton,
            ToastDisplayImage,
            ToastImage,
        )
        toast = Toast(
            text_fields=["Новый чек-лист", file_path.name],
            launch_action=str(file_path),       # click on body
            on_activated=_on_activated,
        )
        # Button — the same path is passed as 'arguments' and surfaces in
        # the callback as event.arguments.
        toast.AddAction(ToastButton(
            content="Открыть папку",
            arguments=str(file_path),
        ))
        icon = _persistent_icon_path()
        if icon is not None:
            try:
                toast.AddImage(ToastDisplayImage(image=ToastImage(icon)))
            except Exception:
                log.exception("Failed to attach toast icon")
        _toaster.show_toast(toast)
    except Exception:
        log.exception("Failed to show toast for %s", file_path)


def notify_overflow(folder_label: str, remaining: int) -> None:
    """A single 'and N more' toast when many files arrive at once."""
    _ensure_setup()
    if _toaster is None:
        return
    try:
        from windows_toasts import Toast
        toast = Toast(text_fields=[
            f"Новые файлы — {folder_label}",
            f"…и ещё {remaining} файлов",
        ])
        _toaster.show_toast(toast)
    except Exception:
        log.exception("Failed to show overflow toast")
