"""Content pipeline orchestration.

This module coordinates the sequential execution of the daily workflow:
script generation, video rendering, local persistence, and platform publishing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.clients.did_client import DidClient, DidRenderResult
from app.clients.openai_client import OpenAIClient, OpenAIScriptResult
from app.config import AppConfig
from app.http_utils import RateLimiter
from app.logging_setup import get_logger
from app.publishers.instagram_publisher import InstagramPublisher, InstagramPublishResult
from app.publishers.tiktok_publisher import TikTokPublisher, TikTokPublishResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    script: OpenAIScriptResult
    did: DidRenderResult
    video_path: Path
    instagram: Optional[InstagramPublishResult]
    tiktok: Optional[TikTokPublishResult]


def _safe_filename_component(value: str) -> str:
    cleaned: str = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_", " ")).strip()
    cleaned = cleaned.replace(" ", "_")
    return cleaned[:60] if cleaned else "video"


def run_daily_pipeline(config: AppConfig, topic_hint: Optional[str] = None) -> PipelineResult:
    output_dir: Path = config.ensure_output_dir()

    rate_limiter: RateLimiter = RateLimiter(
        requests_per_minute=config.requests_per_minute,
        min_jitter_seconds=config.min_jitter_seconds,
        max_jitter_seconds=config.max_jitter_seconds,
    )

    openai: OpenAIClient = OpenAIClient(
        api_key=config.openai_api_key,
        model=config.openai_model,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )
    did: DidClient = DidClient(
        api_key=config.did_api_key,
        base_url=config.did_base_url,
        source_image_url=config.did_source_image_url,
        voice_id=config.did_voice_id,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )

    logger.info("Generating daily script.")
    script: OpenAIScriptResult = openai.generate_daily_short_script(topic_hint=topic_hint)

    now: datetime = datetime.now(timezone.utc)
    timestamp: str = now.strftime("%Y%m%d_%H%M%S")
    name_part: str = _safe_filename_component(script.title)
    video_path: Path = output_dir / f"{timestamp}_{name_part}.mp4"

    logger.info("Rendering talking-head video with D-ID.")
    did_result: DidRenderResult = did.render_talking_head_video(script_text=script.script, output_path=video_path)
    logger.info("Video saved to %s", str(video_path))

    caption_parts: list[str] = [script.title, "", script.script]
    if script.hashtags:
        caption_parts.append("")
        caption_parts.append(" ".join(f"#{tag.lstrip('#')}" for tag in script.hashtags))
    caption: str = "\n".join(caption_parts).strip()

    instagram_result: Optional[InstagramPublishResult] = None
    tiktok_result: Optional[TikTokPublishResult] = None

    instagram: InstagramPublisher = InstagramPublisher(
        access_token=config.ig_access_token,
        user_id=config.ig_user_id,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )
    tiktok: TikTokPublisher = TikTokPublisher(
        access_token=config.tiktok_access_token,
        open_id=config.tiktok_open_id,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )

    try:
        logger.info("Publishing to Instagram Reels.")
        instagram_result = instagram.publish_reel(video_path=video_path, caption=caption)
    except Exception as exc:  # noqa: BLE001
        logger.error("Instagram publishing step failed.", exc_info=True)

    try:
        logger.info("Publishing to TikTok.")
        tiktok_result = tiktok.publish_video(video_path=video_path, caption=caption)
    except Exception as exc:  # noqa: BLE001
        logger.error("TikTok publishing step failed.", exc_info=True)

    return PipelineResult(
        script=script,
        did=did_result,
        video_path=video_path,
        instagram=instagram_result,
        tiktok=tiktok_result,
    )

