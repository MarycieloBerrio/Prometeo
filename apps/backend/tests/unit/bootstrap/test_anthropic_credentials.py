"""ANTHROPIC_API_KEY in a .env file must reach the Anthropic client.

pydantic-settings reads .env into Settings but does not export it to os.environ, where the
SDK looks. These tests use a dummy key and never call the API.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.adapters.outbound.retrieval.keyword_retriever import KeywordRetriever
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.settings import Settings

DUMMY = "sk-ant-test-not-a-real-key"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("ANTHROPIC_API_KEY", "PROMETEO_ANTHROPIC_API_KEY", "PROMETEO_EXPLAINER"):
        monkeypatch.delenv(var, raising=False)


def _env_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def test_key_is_read_from_dotenv(tmp_path: Path) -> None:
    s = Settings(_env_file=_env_file(tmp_path, f"ANTHROPIC_API_KEY={DUMMY}\n"))
    assert s.anthropic_key() == DUMMY


def test_real_environment_variable_wins_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
    s = Settings(_env_file=_env_file(tmp_path, f"ANTHROPIC_API_KEY={DUMMY}\n"))
    assert s.anthropic_key() == "sk-ant-from-env"


@pytest.mark.parametrize("body", ["", "ANTHROPIC_API_KEY=\n", "ANTHROPIC_API_KEY=   \n"])
def test_blank_or_missing_key_means_unset(tmp_path: Path, body: str) -> None:
    assert Settings(_env_file=_env_file(tmp_path, body)).anthropic_key() is None


def test_key_is_not_leaked_by_repr(tmp_path: Path) -> None:
    s = Settings(_env_file=_env_file(tmp_path, f"ANTHROPIC_API_KEY={DUMMY}\n"))
    assert DUMMY not in repr(s) and DUMMY not in str(s.model_dump())


def test_container_passes_dotenv_key_to_the_client(tmp_path: Path) -> None:
    env = _env_file(tmp_path, f"ANTHROPIC_API_KEY={DUMMY}\nPROMETEO_EXPLAINER=anthropic\n")
    settings = Settings(_env_file=env)
    container = build_container(
        settings, trials=JsonTrialRepository([]), documents=KeywordRetriever(None)
    )
    explainer = container.assistant._explainer
    assert explainer._client.api_key == DUMMY  # type: ignore[attr-defined]
