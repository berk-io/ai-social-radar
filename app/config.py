"""Configuration management.

This module loads sensitive configuration values from environment variables,
validates required settings, and provides a typed configuration object for the
pipeline components.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)

    did_api_key: str = Field(min_length=1)
    did_base_url: str = Field(default="https://api.d-id.com", min_length=1)
    did_source_image_url: str = Field(min_length=1)
    did_voice_id: str = Field(default="en-US-JennyNeural", min_length=1)

    ig_access_token: Optional[str] = None
    ig_user_id: Optional[str] = None

    tiktok_access_token: Optional[str] = None
    tiktok_open_id: Optional[str] = None

    requests_per_minute: int = Field(default=50, ge=1, le=6000)
    min_jitter_seconds: float = Field(default=0.6, ge=0.0, le=60.0)
    max_jitter_seconds: float = Field(default=2.2, ge=0.0, le=60.0)
    http_timeout_seconds: float = Field(default=45.0, ge=1.0, le=300.0)

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

    import os

    config: AppConfig = AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        did_api_key=os.getenv("DID_API_KEY", ""),
        did_base_url=os.getenv("DID_BASE_URL", "https://api.d-id.com"),
        did_source_image_url=os.getenv("DID_SOURCE_IMAGE_URL", ""),
        did_voice_id=os.getenv("DID_VOICE_ID", "en-US-JennyNeural"),
        ig_access_token=os.getenv("IG_ACCESS_TOKEN"),
        ig_user_id=os.getenv("IG_USER_ID"),
        tiktok_access_token=os.getenv("TIKTOK_ACCESS_TOKEN"),
        tiktok_open_id=os.getenv("TIKTOK_OPEN_ID"),
        requests_per_minute=int(os.getenv("REQUESTS_PER_MINUTE", "50")),
        min_jitter_seconds=float(os.getenv("MIN_JITTER_SECONDS", "0.6")),
        max_jitter_seconds=float(os.getenv("MAX_JITTER_SECONDS", "2.2")),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "45")),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
    )
    return config

