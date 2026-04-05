"""Media editor.

This module merges a silent or ambient background video with Text-to-Speech audio and
a centered text label using MoviePy, producing a single H.264-friendly MP4 for distribution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.logging_setup import get_logger

logger = get_logger(__name__)

_VideoFileClip: Any = None
_AudioFileClip: Any = None
_CompositeVideoClip: Any = None
_TextClip: Any = None


def _load_moviepy() -> tuple[Any, Any, Any, Any]:
    global _VideoFileClip, _AudioFileClip, _CompositeVideoClip, _TextClip
    if _VideoFileClip is not None:
        return _VideoFileClip, _AudioFileClip, _CompositeVideoClip, _TextClip

    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip
    except ImportError:
        from moviepy import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip  # type: ignore[no-redef]

    _VideoFileClip = VideoFileClip
    _AudioFileClip = AudioFileClip
    _CompositeVideoClip = CompositeVideoClip
    _TextClip = TextClip
    return VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip


def compose_word_lesson_video(
    background_video_path: Path,
    narration_audio_path: Path,
    overlay_text: str,
    output_path: Path,
    font_size: Optional[int] = None,
) -> Path:
    """Attach narration audio to the background clip, overlay centered text, and export MP4."""

    if not background_video_path.is_file():
        raise FileNotFoundError(str(background_video_path))
    if not narration_audio_path.is_file():
        raise FileNotFoundError(str(narration_audio_path))
    if not overlay_text.strip():
        raise ValueError("overlay_text must not be empty")

    VideoFileClip: Any
    AudioFileClip: Any
    CompositeVideoClip: Any
    TextClip: Any
    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip = _load_moviepy()

    video_clip: Any = None
    audio_clip: Any = None
    text_clip: Any = None
    composite: Any = None

    try:
        try:
            video_clip = VideoFileClip(str(background_video_path))
            audio_clip = AudioFileClip(str(narration_audio_path))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load source media clips.", exc_info=True)
            raise RuntimeError("Failed to load source media clips") from exc

        try:
            duration: float = float(min(video_clip.duration, audio_clip.duration))
            if duration <= 0:
                raise RuntimeError("Computed composite duration is not positive")

            video_clip = video_clip.subclip(0, duration)
            audio_clip = audio_clip.subclip(0, duration)
            video_with_audio: Any = video_clip.set_audio(audio_clip)

            fs: int = font_size if font_size is not None else max(48, int(video_with_audio.h * 0.09))

            try:
                text_clip = TextClip(
                    overlay_text,
                    fontsize=fs,
                    color="white",
                    stroke_color="black",
                    stroke_width=2,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "TextClip creation failed. If ImageMagick is not installed, install it or configure MoviePy.",
                    exc_info=True,
                )
                raise RuntimeError("Text overlay creation failed") from exc

            text_clip = text_clip.set_position("center").set_duration(duration)

            composite = CompositeVideoClip([video_with_audio, text_clip], size=video_with_audio.size)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to build composite timeline.", exc_info=True)
            raise RuntimeError("Failed to build composite timeline") from exc

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            composite.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",
                fps=video_clip.fps if getattr(video_clip, "fps", None) else 30,
                threads=4,
                logger=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Video export failed.", exc_info=True)
            raise RuntimeError("Video export failed") from exc

        return output_path.resolve()

    finally:
        for clip in (composite, text_clip, video_clip, audio_clip):
            if clip is None:
                continue
            try:
                clip.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to close a MoviePy clip cleanly.", exc_info=True)
