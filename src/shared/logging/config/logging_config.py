import logging.config
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.shared.config import get_paths_config
from src.shared.logging.infrastructure.logging.logger_adapter import LoggerAdapter
from src.shared.logging.spec import root_logger_guard
from src.shared.logging.spec.spec_loader import SpecLoader
from src.shared.logging.spec.spec_validator import SpecValidator

load_dotenv(override=True)


def setup_logging() -> LoggerAdapter:
    spec = SpecLoader().load()
    config = spec["config"]
    validation = spec["validation"]

    is_valid, warnings = SpecValidator().validate(config, validation)
    if not is_valid:
        for w in warnings:
            print(f"[LoggerConfig] Validation warning: {w}", file=sys.stderr)
        spec = SpecLoader().load(path="__fallback__")  # triggers fallback
        config = spec["config"]
        validation = spec["validation"]

    # Inject tech_logger
    logs_dir = get_paths_config()["directory"]
    logs_path = str(Path(logs_dir) / "logs.log")
    Path(logs_dir).mkdir(parents=True, exist_ok=True)

    config["formatters"]["tech_file"] = {
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
    config["handlers"]["tech_file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "DEBUG",
        "formatter": "tech_file",
        "filename": logs_path,
        "maxBytes": 10485760,
        "backupCount": 5,
        "encoding": "utf-8",
    }
    config["loggers"]["tech_logger"] = {
        "level": "DEBUG",
        "handlers": ["tech_file"],
        "propagate": False,
    }

    # Crea la carpeta de todo handler que escriba a archivo (hoy solo tech_file)
    for handler in config.get("handlers", {}).values():
        if "filename" in handler:
            Path(handler["filename"]).parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(config)

    if validation.get("forbid_root_mutation"):
        root_logger_guard.install()

    LoggerAdapter.configure(validation.get("allowed_levels", []))

    return LoggerAdapter("user_logger")
