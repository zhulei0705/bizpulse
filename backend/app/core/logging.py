import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


def configure_logging() -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    app_file = RotatingFileHandler(
        log_dir / "application.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    app_file.setFormatter(formatter)
    root.addHandler(app_file)

    error_file = RotatingFileHandler(
        log_dir / "error.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(formatter)
    root.addHandler(error_file)
