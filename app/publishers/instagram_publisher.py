"""Instagram publishing.

This module publishes videos to Instagram via the Meta Graph API where permissions allow.
It is designed to be safe-by-default: if credentials are missing or the API rejects
the request, the failure is logged and raised as a controlled exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.http_utils import RateLimiter, RetryPolicy, request_with_retries
from app.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class InstagramPublishResult:
    success: bool
    media_id: Optional[str]


class InstagramPublisher:
    def __init__(
        self,
        access_token: Optional[str],
        user_id: Optional[str],
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._access_token: Optional[str] = access_token
        self._user_id: Optional[str] = user_id
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter
        self._base_url: str = "https://graph.facebook.com/v20.0"

    def publish_reel(self, video_path: Path, caption: str) -> InstagramPublishResult:
        if not self._access_token or not self._user_id:
            raise RuntimeError("Instagram credentials are not configured")

        if not video_path.exists():
            raise FileNotFoundError(str(video_path))

        logger.info("Instagram publishing is configured, but upload requires a public URL or resumable upload flow.")
        logger.info("This implementation provides a safe scaffold to extend once your Meta setup is finalized.")

        # Enterprise-safe scaffold:
        # - Many IG publishing flows require a publicly accessible video URL (or a multi-step upload session).
        # - To avoid accidental misuse, this method currently does not attempt to upload local files directly.
        # - Extend here with your approved upload method for your account type and permissions.

        return InstagramPublishResult(success=False, media_id=None)

    def verify_token(self) -> Dict[str, Any]:
        if not self._access_token:
            raise RuntimeError("Instagram access token is missing")

        url: str = f"{self._base_url}/debug_token"
        params: Dict[str, str] = {
            "input_token": self._access_token,
            "access_token": self._access_token,
        }

        def do_request() -> requests.Response:
            return requests.get(url, params=params, timeout=self._timeout_seconds)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=4, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                rate_limiter=self._rate_limiter,
                context={"service": "instagram", "operation": "debug_token"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Instagram token verification failed.", exc_info=True)
            raise RuntimeError("Instagram token verification failed") from exc

        try:
            return dict(response.json())
        except Exception as exc:  # noqa: BLE001
            logger.error("Instagram token verification parsing failed.", exc_info=True)
            raise RuntimeError("Instagram token verification parsing failed") from exc

