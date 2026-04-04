"""Logging setup.

This module centralizes application logging configuration to ensure consistent,
structured logs across the pipeline and external API integrations.
"""

from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: int = logging.INFO) -> None:
    logger: logging.Logger = logging.getLogger()
    logger.setLevel(level)

    if logger.handlers:
        return

    handler: logging.Handler = logging.StreamHandler()
    formatter: logging.Formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name)

