"""Application coordinator: wires UI, scanner, tray, and persistent state."""
from __future__ import annotations

import logging
import threading
import tkinter as tk

from notifier import notify_new_file, notify_overflow
from scanner import (
    MAX_TOASTS_PER_FOLDER_PER_SCAN,
    ScanCycleResult,
    ScannerService,
    latest_file,
)
from state import load_config, load_state, save_config, save_state
from tray import TrayIcon
from ui import MainWindow

log = logging.getLogger(__name__)


class App:
    def __init__(self) -> None:
        self._config = load_config()
        self._state = load_state()
        self._state_lock = threading.Lock()
        self._quitting = False

        self.root = tk.Tk()
        self.window = MainWindow(
            root=self.root,
            initial_paths=self._config,
            on_folder_chosen=self._on_folder_chosen,
            on_scan_now=self._trigger_scan,
            on_close_to_tray=self._hide_to_tray,
        )

        self.scanner = ScannerService(
            get_config=lambda: self._config,
            get_state=self._snapshot_state,
            save_state=self._commit_state,
            on_cycle_done=self._on_cycle_done,
            on_status=self._on_status,
        )

        self.tray = TrayIcon(
            on_show=self._show_from_tray,
            on_scan_now=self._trigger_scan,
            on_quit=self._quit,
        )

    def run(self) -> None:
        self.tray.start()
        if any(self._config.values()):
            self.scanner.start()
        else:
            self._post(lambda: self.window.set_status("выберите папку"))
        self.root.mainloop()

    # --- UI callbacks ---
    def _on_folder_chosen(self, key: str, path: str) -> None:
        previous = self._config.get(key)
        self._config[key] = path
        try:
            save_config(self._config)
        except Exception:
            log.exception("Failed to persist config.json")

        if previous != path:
            with self._state_lock:
                self._state.pop(key, None)
                try:
                    save_state(self._state)
                except Exception:
                    log.exception("Failed to persist state.json after folder change")
            self._post(lambda k=key: self.window.set_latest(k, None))

        self.scanner.trigger_now()

    def _trigger_scan(self) -> None:
        self.scanner.trigger_now()

    def _hide_to_tray(self) -> None:
        self.window.hide()

    # --- tray callbacks ---
    def _show_from_tray(self) -> None:
        self._post(self.window.show)

    def _quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        log.info("Quit requested")
        self.scanner.stop()
        self.tray.stop()
        self._post(self.root.destroy)

    # --- state plumbing (called from scanner thread) ---
    def _snapshot_state(self) -> dict:
        with self._state_lock:
            import copy
            return copy.deepcopy(self._state)

    def _commit_state(self, new_state: dict) -> None:
        with self._state_lock:
            self._state = new_state
            try:
                save_state(self._state)
            except Exception:
                log.exception("Failed to persist state.json")

    # --- scanner callbacks ---
    def _on_status(self, text: str) -> None:
        self._post(lambda: self.window.set_status(text))

    def _on_cycle_done(self, cycle: ScanCycleResult) -> None:
        for r in cycle.results:
            if r.error:
                msg = f"ошибка ({r.folder_key}): {r.error}"
                self._post(lambda m=msg: self.window.set_status(m))
                self._post(lambda k=r.folder_key: self.window.set_latest(k, None))
                continue

            newest = latest_file(r.current, r.new_files)
            self._post(lambda k=r.folder_key, p=newest:
                       self.window.set_latest(k, p))

            if r.had_baseline and r.new_files:
                ordered = sorted(
                    r.new_files,
                    key=lambda p: (r.current.get(p, {}).get("mtime", 0.0), p),
                    reverse=True,
                )
                for path in ordered[:MAX_TOASTS_PER_FOLDER_PER_SCAN]:
                    notify_new_file(path)
                remaining = len(ordered) - MAX_TOASTS_PER_FOLDER_PER_SCAN
                if remaining > 0:
                    label = "Папка 1" if r.folder_key == "folder1" else "Папка 2"
                    notify_overflow(label, remaining)

        self._post(lambda: self.window.set_next_run(self.scanner.next_run_epoch))
        self._post(lambda: self.window.set_status("ожидание"))

    # --- helpers ---
    def _post(self, fn) -> None:
        try:
            self.root.after(0, fn)
        except RuntimeError:
            pass
