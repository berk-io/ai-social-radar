"""TikTok publishing.

This module is a safe-by-default scaffold for publishing videos to TikTok using
TikTok's Content Posting API, dependent on your account permissions.
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
class TikTokPublishResult:
    success: bool
    publish_id: Optional[str]


class TikTokPublisher:
    def __init__(
        self,
        access_token: Optional[str],
        open_id: Optional[str],
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._access_token: Optional[str] = access_token
        self._open_id: Optional[str] = open_id
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter
        self._base_url: str = "https://open.tiktokapis.com/v2"

    def publish_video(self, video_path: Path, caption: str) -> TikTokPublishResult:
        if not self._access_token or not self._open_id:
            raise RuntimeError("TikTok credentials are not configured")

        if not video_path.exists():
            raise FileNotFoundError(str(video_path))

        logger.info("TikTok publishing is configured, but posting requires an approved upload flow and permissions.")
        logger.info("This implementation provides a safe scaffold to extend once your TikTok setup is finalized.")
        return TikTokPublishResult(success=False, publish_id=None)

    def verify_token(self) -> Dict[str, Any]:
        if not self._access_token:
            raise RuntimeError("TikTok access token is missing")

        url: str = f"{self._base_url}/user/info/"
        headers: Dict[str, str] = {"Authorization": f"Bearer {self._access_token}"}
        params: Dict[str, str] = {"fields": "open_id,union_id,avatar_url,display_name"}

        def do_request() -> requests.Response:
            return requests.get(url, headers=headers, params=params, timeout=self._timeout_seconds)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=4, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                rate_limiter=self._rate_limiter,
                context={"service": "tiktok", "operation": "user_info"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("TikTok token verification failed.", exc_info=True)
            raise RuntimeError("TikTok token verification failed") from exc

        try:
            return dict(response.json())
        except Exception as exc:  # noqa: BLE001
            logger.error("TikTok token verification parsing failed.", exc_info=True)
            raise RuntimeError("TikTok token verification parsing failed") from exc

