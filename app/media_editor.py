"""Media editor.

This module orchestrates the merging of a background video clip with Text-to-Speech audio.
It implements video looping architecture to accommodate variable-length audio tracks.
It safely handles paths with or without text overlays and ensures audio synchronization
before outputting a standardized H.264 MP4 file.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Optional

from app.logging_setup import get_logger

logger = get_logger(__name__)

_VideoFileClip: Any = None
_AudioFileClip: Any = None
_CompositeVideoClip: Any = None
_TextClip: Any = None
_concatenate_videoclips: Any = None

def _load_moviepy() -> tuple[Any, Any, Any, Any, Any]:
    global _VideoFileClip, _AudioFileClip, _CompositeVideoClip, _TextClip, _concatenate_videoclips
    if _VideoFileClip is not None:
        return _VideoFileClip, _AudioFileClip, _CompositeVideoClip, _TextClip, _concatenate_videoclips

    try:
        from moviepy.editor import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip, concatenate_videoclips
    except ImportError:
        from moviepy import AudioFileClip, CompositeVideoClip, TextClip, VideoFileClip, concatenate_videoclips  # type: ignore[no-redef]

    _VideoFileClip = VideoFileClip
    _AudioFileClip = AudioFileClip
    _CompositeVideoClip = CompositeVideoClip
    _TextClip = TextClip
    _concatenate_videoclips = concatenate_videoclips
    return VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips

def compose_word_lesson_video(
    background_video_path: Path,
    narration_audio_path: Path,
    overlay_text: str,
    output_path: Path,
    font_size: Optional[int] = None,
) -> Path:
    """Attach narration audio, loop background video to match audio length, and export MP4."""
    if not background_video_path.is_file():
        raise FileNotFoundError(str(background_video_path))
    if not narration_audio_path.is_file():
        raise FileNotFoundError(str(narration_audio_path))

    VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips = _load_moviepy()

    video_clip: Any = None
    audio_clip: Any = None
    text_clip: Any = None
    final_clip: Any = None
    looped_video: Any = None

    try:
        try:
            video_clip = VideoFileClip(str(background_video_path))
            audio_clip = AudioFileClip(str(narration_audio_path))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load source media clips.", exc_info=True)
            raise RuntimeError("Failed to load source media clips") from exc

        try:
            video_duration: float = float(video_clip.duration)
            audio_duration: float = float(audio_clip.duration)

            if video_duration <= 0 or audio_duration <= 0:
                raise RuntimeError("Computed composite duration is not positive")

            # 1. Calculate and apply loops to the video sequence
            required_loops: int = math.ceil(audio_duration / video_duration)
            looped_video = concatenate_videoclips([video_clip] * required_loops)

            # 2. Trim the looped video strictly to the audio duration
            try:
                looped_video = looped_video.subclipped(0, audio_duration)
            except AttributeError:
                looped_video = looped_video.subclip(0, audio_duration)

            # 3. Explicitly attach the audio track AFTER looping and trimming
            try:
                video_with_audio: Any = looped_video.with_audio(audio_clip)
            except AttributeError:
                video_with_audio: Any = looped_video.set_audio(audio_clip)

            # 4. Check for overlay text requirement
            has_text = bool(overlay_text and overlay_text.strip())

            if not has_text:
                # Direct bypass: No text needed, use the perfectly synced video
                final_clip = video_with_audio
                final_clip.duration = audio_duration
            else:
                # Apply text rendering only if explicitly requested
                fs: int = font_size if font_size is not None else max(48, int(video_with_audio.h * 0.09))
                font_path = "C:/Windows/Fonts/arial.ttf"
                
                try:
                    text_clip = TextClip(
                        text=overlay_text.strip(), font_size=fs, color="white",
                        stroke_color="black", stroke_width=2,
                        font=font_path if os.path.exists(font_path) else None
                    )
                except Exception as e:
                    logger.warning("Font implementation failed, falling back to default.", exc_info=True)
                    try:
                        text_clip = TextClip(text=overlay_text.strip(), font_size=fs, color="white", stroke_color="black", stroke_width=2)
                    except Exception as exc:
                        logger.error("TextClip creation failed.", exc_info=True)
                        raise RuntimeError("Text overlay creation failed") from exc

                try:
                    text_clip = text_clip.with_position("center").with_duration(audio_duration)
                except AttributeError:
                    text_clip = text_clip.set_position("center").set_duration(audio_duration)

                final_clip = CompositeVideoClip([video_with_audio, text_clip], size=video_with_audio.size)
                
                # Double-lock audio binding for CompositeVideoClip
                try:
                    final_clip = final_clip.with_audio(audio_clip)
                except AttributeError:
                    final_clip = final_clip.set_audio(audio_clip)
                    
                final_clip.duration = audio_duration
            
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to build composite timeline.", exc_info=True)
            raise RuntimeError("Failed to build composite timeline") from exc

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_clip.write_videofile(
                str(output_path),
                codec="libx264",
                audio_codec="aac",  # Critical for audio encoding
                fps=video_clip.fps if getattr(video_clip, "fps", None) else 30,
                threads=4,
                logger=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Video export failed.", exc_info=True)
            raise RuntimeError("Video export failed") from exc

        return output_path.resolve()

    finally:
        for clip in (final_clip, looped_video, text_clip, video_clip, audio_clip):
            if clip is None:
                continue
            try:
                clip.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to close a MoviePy clip cleanly.", exc_info=True)