"""HTTP utilities.

This module provides enterprise-safe HTTP behaviors: request throttling,
rate-limit handling, retries with exponential backoff, and jitter to avoid
bursty traffic patterns.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import requests

from app.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_sleep_seconds: float = 1.0
    max_sleep_seconds: float = 30.0


class RateLimiter:
    def __init__(self, requests_per_minute: int, min_jitter_seconds: float, max_jitter_seconds: float) -> None:
        self._rpm: int = max(1, requests_per_minute)
        self._min_jitter: float = max(0.0, min_jitter_seconds)
        self._max_jitter: float = max(self._min_jitter, max_jitter_seconds)
        self._min_interval_seconds: float = 60.0 / float(self._rpm)
        self._last_request_time: float = 0.0

    def sleep_before_request(self) -> None:
        now: float = time.monotonic()
        elapsed: float = now - self._last_request_time
        required: float = self._min_interval_seconds
        delay: float = max(0.0, required - elapsed)
        jitter: float = random.uniform(self._min_jitter, self._max_jitter) if self._max_jitter > 0.0 else 0.0
        total_sleep: float = delay + jitter
        if total_sleep > 0:
            time.sleep(total_sleep)
        self._last_request_time = time.monotonic()


def _compute_backoff_seconds(attempt: int, policy: RetryPolicy) -> float:
    exponential: float = policy.base_sleep_seconds * (2.0 ** max(0, attempt - 1))
    jitter: float = random.uniform(0.0, 1.0)
    return min(policy.max_sleep_seconds, exponential + jitter)


def request_with_retries(
    request_fn: Callable[[], requests.Response],
    policy: RetryPolicy,
    rate_limiter: Optional[RateLimiter] = None,
    context: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    ctx: Dict[str, Any] = context or {}
    last_error: Optional[BaseException] = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            if rate_limiter is not None:
                rate_limiter.sleep_before_request()

            response: requests.Response = request_fn()

            if response.status_code in (429, 500, 502, 503, 504):
                retry_after: Optional[str] = response.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        sleep_seconds: float = float(retry_after)
                    except ValueError:
                        sleep_seconds = _compute_backoff_seconds(attempt, policy)
                else:
                    sleep_seconds = _compute_backoff_seconds(attempt, policy)

                logger.warning(
                    "Transient HTTP status %s. Retrying in %.2fs. Context=%s",
                    response.status_code,
                    sleep_seconds,
                    ctx,
                )
                time.sleep(sleep_seconds)
                continue

            response.raise_for_status()
            return response

        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_error = exc
            sleep_seconds = _compute_backoff_seconds(attempt, policy)
            logger.warning(
                "HTTP attempt %s/%s failed (%s). Retrying in %.2fs. Context=%s",
                attempt,
                policy.max_attempts,
                type(exc).__name__,
                sleep_seconds,
                ctx,
            )
            time.sleep(sleep_seconds)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.error("Unexpected HTTP error. Context=%s", ctx, exc_info=True)
            break

    if last_error is not None:
        raise RuntimeError(f"HTTP request failed after {policy.max_attempts} attempts") from last_error
    raise RuntimeError("HTTP request failed without exception details")

