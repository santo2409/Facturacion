import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)


def setup_logging():
    logs = Path(os.getenv("DIRECTORY")) / "logs.txt"
    logs.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                logs,
                maxBytes=10485760,  # 10MB
                backupCount=5,
            ),
        ],
    )
