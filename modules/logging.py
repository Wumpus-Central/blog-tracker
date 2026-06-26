"""Loguru sink configuration.

Kept out of main.py so importing the engine (e.g. from tests) does not
mutate the global logger as a side effect. Call setup_logging() once
from the entrypoint.
"""
import sys
from loguru import logger


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )