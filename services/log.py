"""Local, privacy-safe logging. Only counts, sheet/file names and states are logged — never cell values."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import LOG_DIR


def get_logger() -> logging.Logger:
    lg = logging.getLogger("switch_hr")
    if not lg.handlers:
        lg.setLevel(logging.INFO)
        try:
            LOG_DIR.mkdir(exist_ok=True)
            h: logging.Handler = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=500_000, backupCount=2,
                                                     encoding="utf-8")
        except OSError:
            h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        lg.addHandler(h)
        lg.propagate = False
    return lg
