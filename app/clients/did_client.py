"""D-ID AI client wrapper (V3 Pro Avatars - Clips API).

This module interacts with the D-ID API to upload narration audio, 
submit a video task using a pre-existing Presenter ID from the user's account,
poll for completion, and download the synchronized video clip.
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
    clip_id: str
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
        presenter_id: str,
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._api_key: str = api_key
        self._presenter_id: str = presenter_id
        self._base_url: str = "https://api.d-id.com"
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter

    def _get_auth(self) -> Tuple[str, str]:
        """Parse D-ID Basic Auth format (username:password)"""
        if ":" not in self._api_key:
            raise ValueError("D-ID API key must be in 'username:password' format.")
        username, password = self._api_key.split(":", 1)
        return username.strip(), password.strip()

    def _upload_audio(self, audio_path: Path) -> str:
        """Uploads the TTS audio file to D-ID and returns the internal URL."""
        url: str = f"{self._base_url}/audios"
        
        logger.info(f"Uploading audio {audio_path.name} to D-ID...")
        
        def do_request() -> requests.Response:
            with open(audio_path, "rb") as f:
                return requests.post(
                    url, 
                    auth=self._get_auth(), 
                    files={"audio": f}, 
                    timeout=self._timeout_seconds
                )

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=3, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                rate_limiter=self._rate_limiter,
                context={"service": "d-id", "operation": "upload_audio"},
            )
        except Exception as exc:
            logger.error("D-ID audio upload failed.", exc_info=True)
            raise RuntimeError("D-ID audio upload failed") from exc

        body = response.json()
        audio_url = body.get("url")
        if not audio_url:
            raise RuntimeError(f"D-ID response missing url. Body: {body}")

        return audio_url

    def create_clip_task(self, audio_path: Path) -> str:
        """Uploads audio and creates a V3 Pro Avatar video clip task."""
        if not self._presenter_id:
            raise ValueError("Presenter ID is missing! Cannot generate D-ID video.")

        audio_url = self._upload_audio(audio_path)

        url: str = f"{self._base_url}/clips"
        payload = {
            "presenter_id": self._presenter_id,
            "script": {
                "type": "audio",
                "audio_url": audio_url
            }
        }

        logger.info(f"Submitting Clip video task to D-ID using Presenter {self._presenter_id}...")
        
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
            context={"service": "d-id", "operation": "create_clip"},
        )
        
        body = response.json()
        clip_id = body.get("id")
        if not clip_id:
            raise RuntimeError(f"D-ID clip creation failed. Body: {body}")
            
        logger.info(f"D-ID task created successfully. Clip ID: {clip_id}")
        return clip_id

    def wait_for_video_url(self, clip_id: str, max_wait_seconds: int = 900) -> str:
        """Polls the D-ID /clips endpoint until the video is ready."""
        url: str = f"{self._base_url}/clips/{clip_id}"

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
                context={"service": "d-id", "operation": "get_clip", "clip_id": clip_id},
            )

            body = response.json()
            status_raw = body.get("status")
            status: str = _normalize_status(status_raw)
            
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
        logger.info(f"Downloading final video from D-ID...")
        
        def do_request() -> requests.Response:
            return requests.get(video_url, timeout=self._timeout_seconds, stream=True)

        response: requests.Response = request_with_retries(
            request_fn=do_request,
            policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
            rate_limiter=self._rate_limiter,
            context={"service": "d-id", "operation": "download_video"},
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    
        return output_path

    def generate_talking_video(self, audio_path: Path, output_path: Path) -> DIDVideoResult:
        """Main orchestrator: creates clip task from audio, waits, and downloads."""
        clip_id: str = self.create_clip_task(audio_path=audio_path)
        video_url: str = self.wait_for_video_url(clip_id=clip_id)
        self.download_video(video_url=video_url, output_path=output_path)
        return DIDVideoResult(clip_id=clip_id, video_url=video_url, local_path=output_path.resolve())