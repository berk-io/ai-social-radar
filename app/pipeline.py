"""Content pipeline orchestration.

This module coordinates the sequential execution of the daily workflow: vocabulary
generation and TTS, talking-head video synthesis via D-ID, media compositing, 
local persistence, and platform publishing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.clients.did_client import DIDClient, DIDVideoResult
from app.clients.openai_client import OpenAIClient, WordLessonResult
from app.config import AppConfig
from app.http_utils import RateLimiter
from app.logging_setup import get_logger
from app.media_editor import compose_word_lesson_video
from app.publishers.instagram_publisher import InstagramPublisher, InstagramPublishResult
from app.publishers.tiktok_publisher import TikTokPublisher, TikTokPublishResult

logger = get_logger(__name__)

@dataclass(frozen=True)
class PipelineResult:
    lesson: WordLessonResult
    did: DIDVideoResult
    final_video_path: Path
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
        tts_model=config.openai_tts_model,
        tts_voice=config.openai_tts_voice,
        timeout_seconds=config.http_timeout_seconds,
        rate_limiter=rate_limiter,
    )
    
    # GÜNCELLEME: presenter_id silindi, yeni API yapısına uyumlu hale getirildi.
    did_client: DIDClient = DIDClient(
        api_key=config.d_id_api_key,
        timeout_seconds=120.0,
        rate_limiter=rate_limiter,
    )

    now: datetime = datetime.now(timezone.utc)
    timestamp: str = now.strftime("%Y%m%d_%H%M%S")

    logger.info("Generating English word lesson and speech audio.")
    lesson: WordLessonResult = openai.produce_word_lesson(
        output_dir=output_dir,
        file_prefix=timestamp,
        topic_hint=topic_hint,
    )

    name_part: str = _safe_filename_component(lesson.english_word)
    raw_video_path: Path = output_dir / f"{timestamp}_{name_part}_did_raw.mp4"
    
    logger.info("Generating synchronized talking video with D-ID AI using custom image.")
    # GÜNCELLEME: image_path parametresi eklendi. Resmin ana dizinde olduğu varsayılır.
    did_result: DIDVideoResult = did_client.generate_talking_video(
        image_path=Path("mandalina_avatar.jpg"),
        audio_path=lesson.audio_path,
        output_path=raw_video_path,
    )

    final_path: Path = output_dir / f"{timestamp}_{name_part}_final.mp4"
    logger.info("Compositing final video with text overlay via MoviePy.")
    try:
        compose_word_lesson_video(
            background_video_path=did_result.local_path,
            narration_audio_path=lesson.audio_path,
            overlay_text=lesson.english_word,
            output_path=final_path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Media composition failed.", exc_info=True)
        raise

    logger.info("Final video saved to %s", str(final_path))

    caption: str = (
        f"{lesson.english_word} — {lesson.turkish_translation}\n"
        f"#English #LearnEnglish #Vocabulary"
    )

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
        instagram_result = instagram.publish_reel(video_path=final_path, caption=caption)
    except Exception as exc:  # noqa: BLE001
        logger.error("Instagram publishing step failed.", exc_info=True)

    try:
        logger.info("Publishing to TikTok.")
        tiktok_result = tiktok.publish_video(video_path=final_path, caption=caption)
    except Exception as exc:  # noqa: BLE001
        logger.error("TikTok publishing step failed.", exc_info=True)

    return PipelineResult(
        lesson=lesson,
        did=did_result,
        final_video_path=final_path,
        instagram=instagram_result,
        tiktok=tiktok_result,
    )