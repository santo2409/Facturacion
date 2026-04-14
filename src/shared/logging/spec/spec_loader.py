import sys
from pathlib import Path

import yaml

_FALLBACK = {
    "config": {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "user_console": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "user_console",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            "user_logger": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            }
        },
    },
    "validation": {
        "allowed_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "max_log_size_mb": 10,
        "required_handlers": ["console"],
        "forbid_root_mutation": True,
    },
}


class SpecLoader:
    def load(self, path: str | None = None) -> dict:
        if path is None:
            path = Path(__file__).parent / "user_logger.yaml"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return {"config": data["config"], "validation": data["validation"]}
        except Exception as e:
            print(f"[SpecLoader] Failed to load spec: {e}. Using fallback.", file=sys.stderr)
            return _FALLBACK
