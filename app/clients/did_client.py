"""D-ID AI client wrapper (V2 Photo Avatars - Talks API).

This module interacts with the D-ID API to upload a custom image, upload narration audio,
submit a video task via the /talks endpoint, poll for completion, and download the video.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from app.http_utils import RateLimiter, RetryPolicy, request_with_retries
from app.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass(frozen=True)
class DIDVideoResult:
    talk_id: str
    video_url: str
    local_path: Path

def _normalize_status(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return str(raw).strip().lower()

class DIDClient:
    def __init__(
        self,
        api_key: str,
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._api_key: str = api_key
        # Not: Artık presenter_id'ye ihtiyacımız yok, onu sildik.
        self._base_url: str = "https://api.d-id.com"
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter

    def _get_auth(self) -> Tuple[str, str]:
        """Parse D-ID Basic Auth format (username:password)"""
        if ":" not in self._api_key:
            raise ValueError("D-ID API key must be in 'username:password' format.")
        username, password = self._api_key.split(":", 1)
        return username.strip(), password.strip()

    def _upload_file(self, file_path: Path, endpoint: str, file_key: str, content_type: str) -> str:
        """Generic file upload functionality for both images and audios."""
        url: str = f"{self._base_url}/{endpoint}"
        logger.info(f"Uploading {file_path.name} to D-ID (/{endpoint})...")

        def do_request() -> requests.Response:
            with open(file_path, "rb") as f:
                return requests.post(
                    url,
                    auth=self._get_auth(),
                    files={file_key: (file_path.name, f, content_type)},
                    timeout=self._timeout_seconds
                )

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=3, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                rate_limiter=self._rate_limiter,
                context={"service": "d-id", "operation": f"upload_{file_key}"},
            )
        except Exception as exc:
            logger.error(f"D-ID {file_key} upload failed.", exc_info=True)
            raise RuntimeError(f"D-ID {file_key} upload failed") from exc

        body = response.json()
        file_url = body.get("url")
        if not file_url:
            raise RuntimeError(f"D-ID response missing url. Body: {body}")

        return file_url

    def create_talk_task(self, image_path: Path, audio_path: Path) -> str:
        """Uploads custom image and audio, then creates a V2 Photo Avatar talk task."""
        
        # Dosya uzantısına bak, PNG ise image/png de, yoksa image/jpeg de
        mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        
        # 1. Resmi yüklüyoruz (Dinamik MIME type ile)
        image_url = self._upload_file(image_path, "images", "image", mime_type)
        
        # 2. Sonra sesi yüklüyoruz
        audio_url = self._upload_file(audio_path, "audios", "audio", "audio/mpeg")

        url: str = f"{self._base_url}/talks"
        payload = {
            "source_url": image_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url
            },
            "config": {
                "stitch": True 
            }
        }

        logger.info("Submitting custom Talk video task to D-ID...")

        def do_request() -> requests.Response:
            return requests.post(
                url,
                auth=self._get_auth(),
                json=payload,
                timeout=self._timeout_seconds
            )

        response: requests.Response = request_with_retries(
            request_fn=do_request,
            policy=RetryPolicy(max_attempts=3, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
            rate_limiter=self._rate_limiter,
            context={"service": "d-id", "operation": "create_talk"},
        )

        body = response.json()
        talk_id = body.get("id")
        if not talk_id:
            raise RuntimeError(f"D-ID talk creation failed. Body: {body}")

        logger.info(f"D-ID task created successfully. Talk ID: {talk_id}")
        return talk_id

    def wait_for_video_url(self, talk_id: str, max_wait_seconds: int = 900) -> str:
        """Polls the D-ID /talks endpoint until the video is ready."""
        url: str = f"{self._base_url}/talks/{talk_id}"
        start: float = time.monotonic()
        last_status: Optional[str] = None
        terminal_fail: set[str] = {"error", "rejected", "failed"}
        terminal_ok: set[str] = {"done"}

        while True:
            elapsed: float = time.monotonic() - start
            if elapsed > float(max_wait_seconds):
                raise TimeoutError("D-ID video generation timed out")

            def do_request() -> requests.Response:
                return requests.get(url, auth=self._get_auth(), timeout=self._timeout_seconds)

            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=4, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                rate_limiter=self._rate_limiter,
                context={"service": "d-id", "operation": "get_talk", "talk_id": talk_id},
            )

            body = response.json()
            status: str = _normalize_status(body.get("status"))

            if status and status != last_status:
                logger.info(f"D-ID task status: {status}")
                last_status = status

            if status in terminal_ok:
                result_url = body.get("result_url")
                if result_url:
                    return result_url

            if status in terminal_fail:
                raise RuntimeError(f"D-ID generation failed: {body}")

            time.sleep(5.0)

    def download_video(self, video_url: str, output_path: Path) -> Path:
        """Downloads the finalized MP4 from D-ID."""
        logger.info("Downloading final video from D-ID...")
        def do_request() -> requests.Response:
            return requests.get(video_url, timeout=self._timeout_seconds, stream=True)

        response: requests.Response = request_with_retries(
            request_fn=do_request,
            policy=RetryPolicy(max_attempts=5, base_sleep_seconds=2.0, max_sleep_seconds=25.0),
            rate_limiter=self._rate_limiter,
            context={"service": "d-id", "operation": "download_video"},
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        return output_path

    def generate_talking_video(self, image_path: Path, audio_path: Path, output_path: Path) -> DIDVideoResult:
        """Main orchestrator: uploads files, creates talk task, waits, and downloads."""
        talk_id: str = self.create_talk_task(image_path=image_path, audio_path=audio_path)
        video_url: str = self.wait_for_video_url(talk_id=talk_id)
        self.download_video(video_url=video_url, output_path=output_path)
        return DIDVideoResult(talk_id=talk_id, video_url=video_url, local_path=output_path.resolve())