"""Configuration management.

This module loads sensitive configuration values from environment variables,
validates required settings, and provides a typed configuration object for the
pipeline components.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)
    openai_tts_model: str = Field(default="tts-1", min_length=1)
    openai_tts_voice: str = Field(default="nova", min_length=1)

    # D-ID AI Settings
    d_id_api_key: str = Field(default="", min_length=0)
    d_id_presenter_id: str = Field(default="", min_length=0)

    ig_access_token: Optional[str] = None
    ig_user_id: Optional[str] = None
    tiktok_access_token: Optional[str] = None
    tiktok_open_id: Optional[str] = None

    requests_per_minute: int = Field(default=50, ge=1, le=6000)
    min_jitter_seconds: float = Field(default=0.6, ge=0.0, le=60.0)
    max_jitter_seconds: float = Field(default=2.2, ge=0.0, le=60.0)
    http_timeout_seconds: float = Field(default=45.0, ge=1.0, le=300.0)

    # Telegram Bot Token buraya eklendi
    telegram_bot_token: str = Field(default="", min_length=0)
    output_dir: str = Field(default="output", min_length=1)

    def ensure_output_dir(self) -> Path:
        output_path: Path = Path(self.output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path


def load_config(dotenv_path: Optional[str] = None) -> AppConfig:
    if dotenv_path is not None: 
        load_dotenv(dotenv_path)
    else:
        load_dotenv()

    # Değişkenleri doğrudan AppConfig içine paslıyoruz
    config: AppConfig = AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", "tts-1"),
        openai_tts_voice=os.getenv("OPENAI_TTS_VOICE", "nova"),
        
        d_id_api_key=os.getenv("D_ID_API_KEY", ""),
        d_id_presenter_id=os.getenv("D_ID_PRESENTER_ID", ""),
        
        ig_access_token=os.getenv("IG_ACCESS_TOKEN"),
        ig_user_id=os.getenv("IG_USER_ID"),
        tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN"),
        tiktok_open_id=os.getenv("TIKTOK_OPEN_ID"),
        
        requests_per_minute=int(os.getenv("REQUESTS_PER_MINUTE", "50")),
        min_jitter_seconds=float(os.getenv("MIN_JITTER_SECONDS", "0.6")),
        max_jitter_seconds=float(os.getenv("MAX_JITTER_SECONDS", "2.2")),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "45")),
        
        # Telegram token'ı buradan sisteme giriyor
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
    )
    return config