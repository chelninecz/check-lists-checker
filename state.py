"""Persistence for user config (folder paths) and known-files state."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

APP_DIR_NAME = "check-list-checker"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path() -> Path:
    return app_data_dir() / "config.json"


def _state_path() -> Path:
    return app_data_dir() / "state.json"


def _atomic_write(path: Path, data: Any) -> None:
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_config() -> dict[str, str | None]:
    """Return {'folder1': path-or-None, 'folder2': path-or-None}."""
    path = _config_path()
    if not path.exists():
        return {"folder1": None, "folder2": None}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Failed to read config.json: %s", e)
        return {"folder1": None, "folder2": None}
    return {
        "folder1": data.get("folder1") or None,
        "folder2": data.get("folder2") or None,
    }


def save_config(config: dict[str, str | None]) -> None:
    _atomic_write(_config_path(), config)


def load_state() -> dict[str, dict[str, dict[str, float]]]:
    """Return {'folder1': {path: {mtime, size}}, ...} or {} if never scanned.

    Absence of a folder key means "no baseline yet" — the first scan for
    that folder must NOT generate notifications.
    """
    path = _state_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Failed to read state.json: %s", e)
        return {}


def save_state(state: dict[str, dict[str, dict[str, float]]]) -> None:
    _atomic_write(_state_path(), state)
