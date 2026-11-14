"""Runtime configuration (env vars prefixed PROMETEO_, see repo-root .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROMETEO_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    data_dir: Path = _REPO_ROOT / "data"
    # Comma-separated JSON files relative to data_dir.
    trial_files: str = "curated/trials.json"
    document_chunks_file: str = "curated/document_chunks.json"
    include_synthetic: bool = False

    trial_store: Literal["json", "postgres"] = "json"
    database_url: str = "postgresql://prometeo:prometeo@localhost:5432/prometeo"

    explainer: Literal["offline", "anthropic"] = "offline"
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    cors_origins: str = "http://localhost:3000"

    def trial_paths(self) -> list[Path]:
        return [self.data_dir / p.strip() for p in self.trial_files.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
