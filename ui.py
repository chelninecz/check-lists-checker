"""Tkinter main window."""
from __future__ import annotations

import logging
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

log = logging.getLogger(__name__)

FOLDER_LABELS = {"folder1": "Папка 1:", "folder2": "Папка 2:"}


def _bundled_icon() -> Path | None:
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    p = base / "assets" / "icon.ico"
    return p if p.exists() else None


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        initial_paths: dict[str, str | None],
        on_folder_chosen: Callable[[str, str], None],
        on_scan_now: Callable[[], None],
        on_close_to_tray: Callable[[], None],
    ) -> None:
        self.root = root
        self._on_folder_chosen = on_folder_chosen
        self._on_scan_now = on_scan_now
        self._on_close_to_tray = on_close_to_tray

        self._next_run_ts: float | None = None
        self._status_extra = "запуск…"
        self._latest: dict[str, str | None] = {"folder1": None, "folder2": None}

        self.path_vars: dict[str, tk.StringVar] = {}
        self.link_vars: dict[str, tk.StringVar] = {}
        self._links: dict[str, tk.Label] = {}

        self._build(initial_paths)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        ico = _bundled_icon()
        if ico is not None:
            try:
                self.root.iconbitmap(str(ico))
            except tk.TclError:
                log.exception("Failed to set window icon")

        self._tick_status()

    def _build(self, initial_paths: dict[str, str | None]) -> None:
        self.root.title("Check-List Checker")
        self.root.geometry("560x280")
        self.root.minsize(460, 260)

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        for idx, key in enumerate(("folder1", "folder2")):
            row = idx * 2
            ttk.Label(frame, text=FOLDER_LABELS[key]).grid(
                row=row, column=0, sticky="w", pady=(0, 2))

            pv = tk.StringVar(value=initial_paths.get(key) or "(не выбрана)")
            self.path_vars[key] = pv
            ttk.Label(frame, textvariable=pv, foreground="#444").grid(
                row=row, column=1, sticky="we", padx=6)

            ttk.Button(
                frame, text="Выбрать…", width=11,
                command=lambda k=key: self._choose(k),
            ).grid(row=row, column=2, sticky="e")

            lv = tk.StringVar(value="Последний новый: —")
            self.link_vars[key] = lv
            link = tk.Label(
                frame, textvariable=lv,
                fg="#888", cursor="arrow", anchor="w", justify="left",
            )
            link.grid(row=row + 1, column=0, columnspan=3,
                      sticky="we", pady=(0, 10))
            link.bind("<Button-1>", lambda e, k=key: self._open_latest(k))
            self._links[key] = link

        ttk.Separator(frame, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="we", pady=(4, 8))

        self.status_var = tk.StringVar(value="Статус: запуск…")
        ttk.Label(frame, textvariable=self.status_var, foreground="#444").grid(
            row=5, column=0, columnspan=2, sticky="w")

        ttk.Button(frame, text="Сканировать сейчас",
                   command=self._on_scan_now).grid(
            row=5, column=2, sticky="e")

    def _choose(self, key: str) -> None:
        path = filedialog.askdirectory(
            title=f"Выберите папку ({FOLDER_LABELS[key].rstrip(':')})",
            mustexist=True,
        )
        if not path:
            return
        path = str(Path(path))
        self.path_vars[key].set(path)
        self._on_folder_chosen(key, path)

    def _open_latest(self, key: str) -> None:
        path = self._latest.get(key)
        if not path:
            return
        try:
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        except Exception:
            log.exception("Failed to open explorer for %s", path)

    # --- public API used by App ---
    def set_latest(self, key: str, path: str | None) -> None:
        self._latest[key] = path
        var = self.link_vars[key]
        label = self._links[key]
        if path:
            var.set(f"Последний новый: {Path(path).name}")
            label.configure(
                fg="#1565c0", cursor="hand2",
                font=("Segoe UI", 9, "underline"),
            )
        else:
            var.set("Последний новый: —")
            label.configure(
                fg="#888", cursor="arrow",
                font=("Segoe UI", 9, ""),
            )

    def set_path_display(self, key: str, path: str | None) -> None:
        self.path_vars[key].set(path or "(не выбрана)")

    def set_status(self, text: str) -> None:
        self._status_extra = text
        self._refresh_status()

    def set_next_run(self, epoch_ts: float | None) -> None:
        self._next_run_ts = epoch_ts
        self._refresh_status()

    def hide(self) -> None:
        self.root.withdraw()

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # --- internals ---
    def _tick_status(self) -> None:
        self._refresh_status()
        self.root.after(15000, self._tick_status)

    def _refresh_status(self) -> None:
        parts: list[str] = []
        if self._status_extra:
            parts.append(self._status_extra)
        if self._next_run_ts is not None:
            remaining = max(0, int(self._next_run_ts - time.time()))
            if remaining >= 60:
                parts.append(f"следующий скан через {remaining // 60} мин")
            else:
                parts.append(f"следующий скан через {remaining} с")
        if not parts:
            parts.append("ожидание")
        self.status_var.set("Статус: " + "; ".join(parts))

    def _handle_close(self) -> None:
        self._on_close_to_tray()
