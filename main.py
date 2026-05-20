"""Entry point for Check-List Checker."""
from __future__ import annotations

import logging
import sys

from app import App


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        App().run()
    except Exception:
        logging.exception("Fatal error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
