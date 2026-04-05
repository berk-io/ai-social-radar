"""Kling AI client wrapper.

This module submits a text-to-video task to the Kling API, polls until the asset is ready,
and downloads a short silent background clip suitable for merging with narration in the
media editor.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.http_utils import RateLimiter, RetryPolicy, request_with_retries
from app.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass(frozen=True)
class KlingVideoResult:
    task_id: str
    video_url: str
    local_path: Path

def _extract_task_id(data: Dict[str, Any]) -> Optional[str]:
    for key in ("task_id", "taskId", "id"):
        raw: Any = data.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    inner: Any = data.get("data")
    if isinstance(inner, dict):
        return _extract_task_id(inner)
    return None

def _extract_video_url(data: Dict[str, Any]) -> Optional[str]:
    for key in ("url", "video_url", "videoUrl", "output_url", "result_url"):
        raw: Any = data.get(key)
        if isinstance(raw, str) and raw.startswith("http"):
            return raw
    inner: Any = data.get("result")
    if isinstance(inner, dict):
        found: Optional[str] = _extract_video_url(inner)
        if found:
            return found
    data_inner: Any = data.get("data")
    if isinstance(data_inner, dict):
        return _extract_video_url(data_inner)
    return None

def _normalize_status(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return str(raw).strip().lower()

class KlingClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._api_key: str = api_key
        self._base_url: str = base_url.rstrip("/")
        self._model: str = model
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter

    def _get_jwt_token(self) -> str:
        if ":" not in self._api_key:
            return self._api_key
        
        ak, sk = self._api_key.split(":", 1)
        ak = ak.strip()
        sk = sk.strip()
        
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": ak,
            "exp": int(time.time()) + 1800,
            "nbf": int(time.time()) - 5
        }
        
        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')
        
        header_enc = b64url(json.dumps(header).encode('utf-8'))
        payload_enc = b64url(json.dumps(payload).encode('utf-8'))
        
        msg = f"{header_enc}.{payload_enc}"
        signature = hmac.new(sk.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).digest()
        sig_enc = b64url(signature)
        
        return f"{msg}.{sig_enc}"

    def _build_visual_prompt(self, english_word: str) -> str:
        return (
            f"Silent cinematic educational B-roll visually illustrating the concept of '{english_word}', "
            "vertical social video, soft lighting, calm motion, stock footage style, no on-screen text, "
            "no logos, no people speaking to camera, ambient visuals only."
        )

    def create_text_to_video_task(self, english_word: str) -> str:
        url: str = f"{self._base_url}/v1/videos/text2video"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._get_jwt_token()}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": self._build_visual_prompt(english_word=english_word),
            "duration": "5",
            "aspect_ratio": "9:16",
        }

        def do_request() -> requests.Response:
            return requests.post(url, headers=headers, json=payload, timeout=self._timeout_seconds)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
                rate_limiter=self._rate_limiter,
                context={"service": "kling", "operation": "text2video"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Kling text-to-video task creation failed.", exc_info=True)
            raise RuntimeError("Kling text-to-video task creation failed") from exc

        try:
            body: Dict[str, Any] = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("Kling create task response parsing failed.", exc_info=True)
            raise RuntimeError("Kling create task response parsing failed") from exc

        task_id: Optional[str] = _extract_task_id(body)
        if not task_id:
            logger.error("Kling response missing task id. Body keys: %s", list(body.keys()))
            raise RuntimeError("Kling response missing task id")

        return task_id

    def wait_for_video_url(self, task_id: str, max_wait_seconds: int = 900) -> str:
        url: str = f"{self._base_url}/v1/videos/{task_id}"
        headers: Dict[str, str] = {"Authorization": f"Bearer {self._get_jwt_token()}"}

        start: float = time.monotonic()
        last_status: Optional[str] = None

        terminal_fail: set[str] = {"failed", "error", "cancelled", "canceled"}
        terminal_ok: set[str] = {"completed", "complete", "success", "succeeded", "done", "succeed"}

        while True:
            elapsed: float = time.monotonic() - start
            if elapsed > float(max_wait_seconds):
                raise TimeoutError("Kling video generation timed out")

            def do_request() -> requests.Response:
                return requests.get(url, headers=headers, timeout=self._timeout_seconds)

            try:
                response: requests.Response = request_with_retries(
                    request_fn=do_request,
                    policy=RetryPolicy(max_attempts=4, base_sleep_seconds=1.0, max_sleep_seconds=15.0),
                    rate_limiter=self._rate_limiter,
                    context={"service": "kling", "operation": "get_video", "task_id": task_id},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Kling polling request failed; retrying.", exc_info=True)
                time.sleep(3.0)
                continue

            try:
                body: Dict[str, Any] = response.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Kling polling JSON parse failed; retrying.", exc_info=True)
                time.sleep(3.0)
                continue

            status_raw: Optional[str] = None
            if isinstance(body.get("status"), str):
                status_raw = body.get("status")
            elif isinstance(body.get("data"), dict) and isinstance(body["data"].get("status"), str):
                status_raw = body["data"]["status"]

            status: str = _normalize_status(status_raw)
            if status and status != last_status:
                logger.info("Kling task status: %s", status)
                last_status = status

            video_url: Optional[str] = _extract_video_url(body)

            if status in terminal_ok and video_url:
                return video_url

            if status in terminal_fail:
                err: Any = body.get("error") or body.get("message")
                raise RuntimeError(f"Kling generation failed: {err!r}")

            if video_url and status in terminal_ok.union({"ready", "finished"}):
                return video_url

            if video_url and not status:
                return video_url

            time.sleep(4.0)

    def download_video(self, video_url: str, output_path: Path) -> Path:
        def do_request() -> requests.Response:
            return requests.get(video_url, timeout=self._timeout_seconds, stream=True)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
                rate_limiter=self._rate_limiter,
                context={"service": "kling", "operation": "download_video"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Kling video download failed.", exc_info=True)
            raise RuntimeError("Kling video download failed") from exc

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        except Exception as exc:  # noqa: BLE001
            logger.error("Writing Kling video file failed.", exc_info=True)
            raise RuntimeError("Writing Kling video file failed") from exc

        return output_path

    def generate_background_video(self, english_word: str, output_path: Path) -> KlingVideoResult:
        task_id: str = self.create_text_to_video_task(english_word=english_word)
        video_url: str = self.wait_for_video_url(task_id=task_id)
        self.download_video(video_url=video_url, output_path=output_path)
        return KlingVideoResult(task_id=task_id, video_url=video_url, local_path=output_path.resolve())