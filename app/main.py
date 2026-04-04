"""Main execution entrypoint.

This module runs the sequential pipeline (text -> video -> publish) using environment-driven
configuration. It is designed for daily scheduled execution.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import load_config
from app.logging_setup import configure_logging, get_logger
from app.pipeline import run_daily_pipeline

logger = get_logger(__name__)


def main(topic_hint: Optional[str] = None) -> int:
    configure_logging(level=logging.INFO)

    try:
        config = load_config()
    except Exception as exc:  # noqa: BLE001
        logger.error("Configuration loading failed.", exc_info=True)
        return 2

    try:
        _ = run_daily_pipeline(config=config, topic_hint=topic_hint)
    except Exception as exc:  # noqa: BLE001
        logger.error("Pipeline failed.", exc_info=True)
        return 1

    logger.info("Pipeline completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

