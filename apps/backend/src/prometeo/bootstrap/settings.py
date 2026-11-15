"""Runtime configuration (env vars prefixed PROMETEO_, see repo-root .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    # The repo-root .env (shared with docker compose) is the one settings file. A .env in the
    # working directory (apps/backend when run via `pnpm dev:api`) is read after it and wins.
    model_config = SettingsConfigDict(
        env_prefix="PROMETEO_", env_file=(_REPO_ROOT / ".env", ".env"), extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    data_dir: Path = _REPO_ROOT / "data"
    # Comma-separated JSON files relative to data_dir.
    trial_files: str = "curated/trials.json"
    document_chunks_file: str = "curated/document_chunks.json"
    include_synthetic: bool = False

    trial_store: Literal["json", "postgres"] = "json"
    database_url: str = "postgresql://prometeo:prometeo@localhost:5432/prometeo"

    # json: keyword search over document_chunks_file. postgres: hybrid full-text + pgvector
    # search over the knowledge base built by `prometeo build-knowledge-base`.
    document_store: Literal["json", "postgres"] = "json"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    psi_base_url: str = "https://psi.nasa.gov"

    explainer: Literal["offline", "anthropic"] = "offline"
    # Model that writes the interpretation when a question does not pick one.
    anthropic_model: str = "claude-sonnet-5-5"
    # Comma-separated models a question may pick instead (the default is always offered).
    anthropic_models: str = "claude-sonnet-5-5,claude-opus-5-5,claude-haiku-5-5"
    anthropic_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    # Read from the environment or from either .env file, under its standard SDK name. A real
    # environment variable wins over .env. Empty means "not set": the SDK then falls back to
    # its own resolution (ANTHROPIC_API_KEY in the process env, or an `ant auth login` profile).
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "PROMETEO_ANTHROPIC_API_KEY"),
    )

    cors_origins: str = "http://localhost:3000"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    def anthropic_key(self) -> str | None:
        """The configured key, or None when unset or blank (never logged or echoed)."""
        if self.anthropic_api_key is None:
            return None
        return self.anthropic_api_key.get_secret_value().strip() or None

    def anthropic_model_choices(self) -> list[str]:
        """Models offered per question: the default first, then the configured list."""
        listed = [m.strip() for m in self.anthropic_models.split(",") if m.strip()]
        return list(dict.fromkeys([self.anthropic_model, *listed]))

    def trial_paths(self) -> list[Path]:
        return [self.data_dir / p.strip() for p in self.trial_files.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
