"""Fixtures for scientific E2E tests against curated BASS-II JSON (not synthetic)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prometeo.bootstrap.api import build_app
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data"
CURATED_TRIALS = DATA_DIR / "curated" / "trials.json"
FLAMEVISION_INDEX = (
    REPO_ROOT / "apps" / "frontend" / "public" / "experiments" / "flamevision" / "index.json"
)
FLAMEVISION_MANIFEST = (
    REPO_ROOT
    / "apps"
    / "frontend"
    / "public"
    / "experiments"
    / "flamevision"
    / "psi25-test-b9"
    / "manifest.json"
)

EXPECTED_CURATED_IDS = frozenset(
    {
        "BASS-II-B16-Vg755",
        "BASS-II-B16-Vg167",
        "BASS-II-B16-Vg083",
        "BASS-II-B16-Vg072",
        "BASS-II-B19-Vg755",
        "BASS-II-B19-Vg167",
        "BASS-II-FILM-100um-SR-extinction-context",
    }
)


@pytest.fixture
def curated_client() -> TestClient:
    """HTTP app wired explicitly to curated NASA data — ignores ambient .env."""
    settings = Settings(
        data_dir=DATA_DIR,
        trial_files="curated/trials.json",
        include_synthetic=False,
        explainer="offline",
    )
    return TestClient(build_app(build_container(settings)))
