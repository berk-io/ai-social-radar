"""OpenAI client wrapper.

This module generates a daily short-form video script using the OpenAI API.
It uses safe retry behavior and consistent JSON parsing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from app.http_utils import RateLimiter, RetryPolicy, request_with_retries
from app.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class OpenAIScriptResult:
    title: str
    script: str
    hashtags: list[str]


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        rate_limiter: RateLimiter,
    ) -> None:
        self._api_key: str = api_key
        self._model: str = model
        self._timeout_seconds: float = timeout_seconds
        self._rate_limiter: RateLimiter = rate_limiter
        self._base_url: str = "https://api.openai.com/v1"

    def generate_daily_short_script(self, topic_hint: Optional[str] = None) -> OpenAIScriptResult:
        prompt_topic: str = topic_hint or "a practical, high-value tip for small businesses"

        system_text: str = (
            "You generate short-form social video scripts for business audiences. "
            "Return only valid JSON."
        )
        user_text: str = (
            "Create a concise talking-head script (20-35 seconds) for today. "
            "Language: English. Tone: professional, clear, helpful. "
            "Structure: hook, 3 bullet steps, closing CTA. "
            "Also provide a short title and 6-10 relevant hashtags. "
            f"Topic hint: {prompt_topic}. "
            "Return JSON with keys: title (string), script (string), hashtags (array of strings)."
        )

        url: str = f"{self._base_url}/chat/completions"
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "temperature": 0.7,
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
                context={"service": "openai", "operation": "generate_script"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI script generation failed.", exc_info=True)
            raise RuntimeError("OpenAI script generation failed") from exc

        try:
            data: Dict[str, Any] = response.json()
            content: str = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI response parsing failed.", exc_info=True)
            raise RuntimeError("OpenAI response parsing failed") from exc

        try:
            parsed: Dict[str, Any] = json.loads(content)
            title: str = str(parsed["title"]).strip()
            script: str = str(parsed["script"]).strip()
            hashtags_raw: Any = parsed.get("hashtags", [])
            hashtags: list[str] = [str(x).strip() for x in list(hashtags_raw) if str(x).strip()]
        except Exception as exc:  # noqa: BLE001
            logger.error("OpenAI JSON content invalid.", exc_info=True)
            raise RuntimeError("OpenAI returned invalid JSON content") from exc

        if not title or not script:
            raise RuntimeError("OpenAI returned empty title or script")

        return OpenAIScriptResult(title=title, script=script, hashtags=hashtags)

