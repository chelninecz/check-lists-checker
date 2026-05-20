"""Folder scanning logic and the background scheduler service."""
from __future__ import annotations

import copy
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 3600.0
MAX_TOASTS_PER_FOLDER_PER_SCAN = 5

FOLDER_KEYS = ("folder1", "folder2")


@dataclass
class FolderScanResult:
    folder_key: str
    folder_path: str | None
    current: dict[str, dict[str, float]]
    new_files: list[str]
    had_baseline: bool
    error: str | None = None


@dataclass
class ScanCycleResult:
    results: list[FolderScanResult] = field(default_factory=list)


def scan_folder(folder_path: str) -> dict[str, dict[str, float]]:
    """Recursively walk folder_path, return {abs_path: {mtime, size}}."""
    out: dict[str, dict[str, float]] = {}
    for root, _dirs, files in os.walk(folder_path):
        for name in files:
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError as e:
                log.warning("stat failed for %s: %s", full, e)
                continue
            out[full] = {"mtime": st.st_mtime, "size": st.st_size}
    return out


def diff_new(old: dict[str, dict[str, float]],
             new: dict[str, dict[str, float]]) -> list[str]:
    """Return paths in `new` that weren't in `old`."""
    return sorted(set(new) - set(old))


def latest_file(meta: dict[str, dict[str, float]],
                candidates: list[str]) -> str | None:
    """Pick the candidate with newest mtime; tie-break alphabetically last."""
    if not candidates:
        return None

    def key(p: str) -> tuple[float, str]:
        m = meta.get(p, {})
        return (m.get("mtime", 0.0), p)

    return max(candidates, key=key)


class ScannerService:
    """Runs scans sequentially in a background thread on a fixed cadence."""

    def __init__(
        self,
        get_config: Callable[[], dict[str, str | None]],
        get_state: Callable[[], dict],
        save_state: Callable[[dict], None],
        on_cycle_done: Callable[[ScanCycleResult], None],
        on_status: Callable[[str], None],
        interval: float = SCAN_INTERVAL_SECONDS,
    ) -> None:
        self._get_config = get_config
        self._get_state = get_state
        self._save_state = save_state
        self._on_cycle_done = on_cycle_done
        self._on_status = on_status
        self._interval = interval

        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._running = threading.Event()
        self._next_run_ts: float | None = None

    def start(self) -> None:
        self._schedule(0.0)

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def trigger_now(self) -> None:
        if self._stop.is_set():
            return
        if self._running.is_set():
            # A scan is already in-flight; let it finish — it will reschedule.
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._schedule(0.0)

    @property
    def next_run_epoch(self) -> float | None:
        return self._next_run_ts

    def _schedule(self, delay: float) -> None:
        if self._stop.is_set():
            return
        self._next_run_ts = time.time() + delay
        t = threading.Timer(delay, self._run_cycle)
        t.daemon = True
        with self._lock:
            self._timer = t
        t.start()

    def _run_cycle(self) -> None:
        if self._stop.is_set():
            return
        self._running.set()
        try:
            self._on_status("сканирование…")
            cycle = self._do_scan()
            self._on_cycle_done(cycle)
        except Exception:
            log.exception("Scan cycle crashed")
        finally:
            self._running.clear()
            if not self._stop.is_set():
                self._schedule(self._interval)

    def _do_scan(self) -> ScanCycleResult:
        config = self._get_config()
        state = copy.deepcopy(self._get_state())
        cycle = ScanCycleResult()

        for key in FOLDER_KEYS:
            path = config.get(key)
            if not path:
                continue
            log.info("Scanning %s = %s", key, path)
            had_baseline = key in state
            known = state.get(key, {})
            try:
                current = scan_folder(path)
            except OSError as e:
                log.warning("Scan failed for %s: %s", path, e)
                cycle.results.append(FolderScanResult(
                    folder_key=key, folder_path=path,
                    current={}, new_files=[],
                    had_baseline=had_baseline, error=str(e),
                ))
                continue

            new_paths = diff_new(known, current) if had_baseline else []
            state[key] = current
            cycle.results.append(FolderScanResult(
                folder_key=key, folder_path=path,
                current=current, new_files=new_paths,
                had_baseline=had_baseline,
            ))

        try:
            self._save_state(state)
        except Exception:
            log.exception("Failed to persist state")
        return cycle
