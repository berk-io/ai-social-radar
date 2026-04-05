"""OpenAI client wrapper.

This module generates a daily English vocabulary lesson (word plus Turkish gloss)
using the OpenAI Chat Completions API, and produces narration audio via the
OpenAI Text-to-Speech API. It uses safe retry behavior and consistent JSON parsing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.http_utils import RateLimiter, RetryPolicy, request_with_retries
from app.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WordLessonResult:
    """Structured result for the English word teaching Reels format."""

    english_word: str
    turkish_translation: str
    audio_path: Path


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        tts_model: str,
        tts_voice: str,
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._api_key: str = api_key
        self._model: str = model
        self._tts_model: str = tts_model
        self._tts_voice: str = tts_voice
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter
        self._base_url: str = "https://api.openai.com/v1"

    def generate_word_lesson_content(self, topic_hint: Optional[str] = None) -> tuple[str, str]:
        """Generate one English word and its Turkish translation (JSON from the chat model)."""

        focus: str = topic_hint or "everyday objects, food, nature, or common verbs suitable for beginners"

        system_text: str = (
            "You support an English vocabulary teaching format for short vertical video. "
            "Return only valid JSON."
        )
        user_text: str = (
            "Pick a single English word appropriate for language learners and give its Turkish translation. "
            f"Theme hint: {focus}. "
            "The English word must be a single word or a short compound where appropriate (e.g. 'to learn' as two words is acceptable). "
            "Return JSON with keys: english_word (string), turkish_translation (string)."
        )

        url: str = f"{self._base_url}/chat/completions"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "temperature": 0.85,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
        }

        def do_request() -> requests.Response:
            return requests.post(url, headers=headers, json=payload, timeout=self._timeout_seconds)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
                rate_limiter=self._rate_limiter,
                context={"service": "openai", "operation": "generate_word_lesson"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI word lesson generation failed.", exc_info=True)
            raise RuntimeError("OpenAI word lesson generation failed") from exc

        try:
            data: Dict[str, Any] = response.json()
            content: str = data["choices"][0]["message"]["content"]
            
            content = content.replace("```json", "").replace("```", "").strip()
            
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI response parsing failed.", exc_info=True)
            raise RuntimeError("OpenAI response parsing failed") from exc

        try:
            parsed: Dict[str, Any] = json.loads(content)
            english_word: str = str(parsed["english_word"]).strip()
            turkish_translation: str = str(parsed["turkish_translation"]).strip()
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI JSON content invalid.", exc_info=True)
            raise RuntimeError("OpenAI returned invalid JSON content") from exc

        if not english_word or not turkish_translation:
            raise RuntimeError("OpenAI returned empty english_word or turkish_translation")

        return english_word, turkish_translation

    def synthesize_speech_to_mp3(self, text: str, output_path: Path) -> Path:
        """Generate spoken audio from text using the OpenAI Text-to-Speech API and save an .mp3 file."""

        if not text.strip():
            raise ValueError("TTS text must not be empty")

        url: str = f"{self._base_url}/audio/speech"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._tts_model,
            "voice": self._tts_voice,
            "input": text,
            "response_format": "mp3",
        }

        def do_request() -> requests.Response:
            return requests.post(url, headers=headers, json=payload, timeout=self._timeout_seconds)

        try:
            response: requests.Response = request_with_retries(
                request_fn=do_request,
                policy=RetryPolicy(max_attempts=5, base_sleep_seconds=1.0, max_sleep_seconds=25.0),
                rate_limiter=self._rate_limiter,
                context={"service": "openai", "operation": "tts_speech"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI TTS request failed.", exc_info=True)
            raise RuntimeError("OpenAI TTS request failed") from exc

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as f:
                f.write(response.content)
        except Exception as exc:  # noqa: BLE001
            logger.error("Writing TTS audio file failed.", exc_info=True)
            raise RuntimeError("Writing TTS audio file failed") from exc

        return output_path

    def produce_word_lesson(
        self,
        output_dir: Path,
        file_prefix: str,
        topic_hint: Optional[str] = None,
    ) -> WordLessonResult:
        """Generate vocabulary labels, write narration to an .mp3 file, and return the complete lesson result."""

        try:
            english_word, turkish_translation = self.generate_word_lesson_content(topic_hint=topic_hint)
        except Exception as exc:  # noqa: BLE001
            logger.error("Word lesson content step failed.", exc_info=True)
            raise

        safe_stem: str = "".join(c for c in english_word if c.isalnum() or c in ("-", "_"))[:40] or "word"
        audio_path: Path = output_dir / f"{file_prefix}_{safe_stem}_speech.mp3"
        narration: str = f"{english_word}. Turkish: {turkish_translation}."

        try:
            self.synthesize_speech_to_mp3(text=narration, output_path=audio_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Word lesson TTS step failed.", exc_info=True)
            raise

        return WordLessonResult(
            english_word=english_word,
            turkish_translation=turkish_translation,
            audio_path=audio_path.resolve(),
        )
