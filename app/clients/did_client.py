"""D-ID client wrapper.

This module creates a talking-head video using D-ID from a script and a static source image.
It polls the rendering job until completion and downloads the resulting .mp4 file.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.http_utils import RateLimiter, RetryPolicy, request_with_retries
from app.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DidRenderResult:
    talk_id: str
    video_url: str


class DidClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        source_image_url: str,
        voice_id: str,
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._api_key: str = api_key
        self._base_url: str = base_url.rstrip("/")
        self._source_image_url: str = source_image_url
        self._voice_id: str = voice_id
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter

    def create_talk(self, script_text: str) -> str:
        url: str = f"{self._base_url}/talks"
        headers: Dict[str, str] = {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "source_url": self._source_image_url,
            "script": {
                "type": "text",
                "input": script_text,
                "provider": {"type": "microsoft", "voice_id": self._voice_id},
            },
        }

        def do_request() -> requests.Response:
            return requests.post(url, headers=headers, json=payload, timeout=self._timeout_seconds)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
                rate_limiter=self._rate_limiter,
                context={"service": "did", "operation": "create_talk"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("D-ID talk creation failed.", exc_info=True)
            raise RuntimeError("D-ID talk creation failed") from exc

        try:
            data: Dict[str, Any] = response.json()
            talk_id: str = str(data["id"])
        except Exception as exc:  # noqa: BLE001
            logger.error("D-ID create talk response parsing failed.", exc_info=True)
            raise RuntimeError("D-ID create talk response parsing failed") from exc

        if not talk_id:
            raise RuntimeError("D-ID returned empty talk id")
        return talk_id

    def wait_for_talk_video_url(self, talk_id: str, max_wait_seconds: int = 600) -> str:
        url: str = f"{self._base_url}/talks/{talk_id}"
        headers: Dict[str, str] = {"Authorization": f"Basic {self._api_key}"}

        start: float = time.monotonic()
        last_status: Optional[str] = None

        while True:
            elapsed: float = time.monotonic() - start
            if elapsed > float(max_wait_seconds):
                raise TimeoutError("D-ID render timed out")

            def do_request() -> requests.Response:
                return requests.get(url, headers=headers, timeout=self._timeout_seconds)

            try:
                response: requests.Response = request_with_retries(
                    request_fn=do_request,
                    policy=RetryPolicy(max_attempts=4, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                    rate_limiter=self._rate_limiter,
                    context={"service": "did", "operation": "get_talk", "talk_id": talk_id},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("D-ID polling failed; continuing.", exc_info=True)
                time.sleep(2.0)
                continue

            try:
                data: Dict[str, Any] = response.json()
                status: str = str(data.get("status", "")).lower()
                result_url: Optional[str] = data.get("result_url")
                error_reason: Optional[str] = data.get("error_reason")
            except Exception as exc:  # noqa: BLE001
                logger.warning("D-ID polling response parsing failed; continuing.", exc_info=True)
                time.sleep(2.0)
                continue

            if status and status != last_status:
                logger.info("D-ID render status updated: %s", status)
                last_status = status

            if status in ("done", "completed") and result_url:
                return str(result_url)

            if status in ("error", "failed"):
                raise RuntimeError(f"D-ID render failed: {error_reason or 'unknown'}")

            time.sleep(3.0)

    def download_video(self, video_url: str, output_path: Path) -> Path:
        headers: Dict[str, str] = {"Authorization": f"Basic {self._api_key}"}

        def do_request() -> requests.Response:
            return requests.get(video_url, headers=headers, timeout=self._timeout_seconds, stream=True)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
                rate_limiter=self._rate_limiter,
                context={"service": "did", "operation": "download_video"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("D-ID video download failed.", exc_info=True)
            raise RuntimeError("D-ID video download failed") from exc

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        except Exception as exc:  # noqa: BLE001
            logger.error("Writing video file failed.", exc_info=True)
            raise RuntimeError("Writing video file failed") from exc

        return output_path

    def render_talking_head_video(self, script_text: str, output_path: Path) -> DidRenderResult:
        talk_id: str = self.create_talk(script_text=script_text)
        video_url: str = self.wait_for_talk_video_url(talk_id=talk_id)
        self.download_video(video_url=video_url, output_path=output_path)
        return DidRenderResult(talk_id=talk_id, video_url=video_url)

