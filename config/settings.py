"""
config/settings.py
──────────────────
Centralised application configuration powered by Pydantic-Settings.
Values are read from environment variables or a .env file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Scraper ───────────────────────────────────────────────
    wuzzuf_base_url: str = Field(
        default="https://wuzzuf.net/search/jobs/",
        description="Base URL for Wuzzuf job search endpoint.",
    )
    scrape_max_pages: int = Field(
        default=50,
        ge=1,
        description="Maximum number of result pages to scrape per query.",
    )
    scrape_headless: bool = Field(
        default=True,
        description="Run Chrome in headless mode.",
    )
    scrape_request_delay_seconds: float = Field(
        default=2.5,
        ge=0.0,
        description="Polite delay (seconds) between consecutive HTTP requests.",
    )

    # ── Output ────────────────────────────────────────────────
    output_dir: Path = Field(
        default=Path("output"),
        description="Directory where CSV/JSON artefacts are written.",
    )
    state_file: Path = Field(
        default=Path("pipeline/state/checkpoint.json"),
        description="Path to the atomic JSON checkpoint file.",
    )

    # ── Logging ───────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Python logging level (DEBUG, INFO, WARNING, ERROR).",
    )

    # ── NLP ───────────────────────────────────────────────────
    fuzzy_match_threshold: int = Field(
        default=85,
        ge=0,
        le=100,
        description="RapidFuzz token-sort-ratio threshold for skill matching.",
    )
    context_window_tokens: int = Field(
        default=6,
        ge=1,
        description="Token radius around a candidate skill for context-window gating.",
    )


settings = Settings()
