"""Entry point for Check-List Checker."""
from __future__ import annotations

import logging
import logging.handlers
import sys

from app import App
from state import app_data_dir


def _setup_logging() -> None:
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    log_path = app_data_dir() / "app.log"
    file_h = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    file_h.setFormatter(fmt)
    root.addHandler(file_h)

    # Console handler: skipped when running as a PyInstaller --windowed bundle
    # (sys.stderr is None there and would crash StreamHandler).
    if sys.stderr is not None:
        stream_h = logging.StreamHandler()
        stream_h.setFormatter(fmt)
        root.addHandler(stream_h)


def main() -> int:
    _setup_logging()
    logging.getLogger(__name__).info("Check-List Checker starting")
    try:
        App().run()
    except Exception:
        logging.exception("Fatal error")
        return 1
    logging.getLogger(__name__).info("Check-List Checker exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
