"""Integrity checks for curated NASA BASS-II evidence (not SYNTHETIC fixtures)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.adapters.outbound.persistence.trial_codec import trial_from_json
from prometeo.bootstrap.api import build_app
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.settings import Settings
from prometeo.domain.experiments.model import DataQuality, Investigation
from prometeo.domain.shared.quantity import dimension_of

REPO_ROOT = Path(__file__).resolve().parents[4]
CURATED_TRIALS = REPO_ROOT / "data" / "curated" / "trials.json"
CURATED_CHUNKS = REPO_ROOT / "data" / "curated" / "document_chunks.json"
MANIFEST = REPO_ROOT / "data" / "sources" / "bass2-manifest.json"


@pytest.fixture(scope="module")
def curated_raw() -> list[dict]:
    assert CURATED_TRIALS.is_file(), f"missing {CURATED_TRIALS}"
    data = json.loads(CURATED_TRIALS.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


@pytest.fixture(scope="module")
def curated_trials(curated_raw: list[dict]):
    return [trial_from_json(raw) for raw in curated_raw]


def test_curated_file_is_nonempty_and_unique(curated_raw: list[dict]) -> None:
    assert len(curated_raw) >= 1
    ids = [r["id"] for r in curated_raw]
    assert len(ids) == len(set(ids))


def test_no_synthetic_investigation_or_quality(curated_trials, curated_raw: list[dict]) -> None:
    for trial in curated_trials:
        assert trial.investigation is not Investigation.SYNTHETIC
        assert not trial.is_synthetic
        for meas in trial.results:
            assert meas.quality is not DataQuality.SYNTHETIC
    for raw in curated_raw:
        assert raw["investigation"] != "SYNTHETIC"


def test_repository_loads_curated_paths(curated_trials) -> None:
    repo = JsonTrialRepository([CURATED_TRIALS])
    loaded = repo.list_all()
    assert len(loaded) == len(curated_trials)
    assert {t.id for t in loaded} == {t.id for t in curated_trials}


def test_provenance_traceable_and_no_localhost(curated_trials) -> None:
    for trial in curated_trials:
        assert trial.provenance.reference
        assert trial.provenance.is_traceable
        for uri in filter(None, [trial.provenance.url]):
            host = (urlparse(uri).hostname or "").lower()
            assert host not in {"localhost", "127.0.0.1"}
            assert not host.endswith(".local")
        for meas in trial.results:
            assert meas.provenance.reference
            assert meas.provenance.is_traceable
            if meas.provenance.url:
                host = (urlparse(meas.provenance.url).hostname or "").lower()
                assert "localhost" not in host
        for media in trial.media:
            host = (urlparse(media.uri).hostname or "").lower()
            assert "localhost" not in host
            assert "127.0.0.1" not in media.uri


def test_units_and_physical_bounds(curated_trials) -> None:
    for trial in curated_trials:
        if trial.oxygen is not None:
            dimension_of(trial.oxygen.unit)
            ox = trial.oxygen.to("%").value if trial.oxygen.unit != "%" else trial.oxygen.value
            if trial.oxygen.unit == "fraction":
                ox = trial.oxygen.value * 100
            assert 0 < ox <= 100
        if trial.ventilation.speed is not None:
            dimension_of(trial.ventilation.speed.unit)
            assert trial.ventilation.speed.canonical() >= 0
        if trial.geometry.thickness is not None:
            dimension_of(trial.geometry.thickness.unit)
            assert trial.geometry.thickness.canonical() > 0
        for meas in trial.results:
            dimension_of(meas.value.unit)
            if meas.name == "flame_spread_rate":
                assert meas.value.canonical() >= 0
            if meas.quality is DataQuality.DERIVED:
                assert meas.method


def test_bass_ii_ids_and_manifest_alignment(curated_raw: list[dict]) -> None:
    assert MANIFEST.is_file()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    curated_ids = {r["id"] for r in curated_raw}
    assert set(manifest["curated_trial_ids"]) == curated_ids
    for tid in curated_ids:
        assert tid.startswith("BASS-II-")


def test_document_chunks_schema_and_no_localhost() -> None:
    chunks = json.loads(CURATED_CHUNKS.read_text(encoding="utf-8"))
    assert isinstance(chunks, list) and len(chunks) >= 1
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))
    for chunk in chunks:
        assert chunk["text"].strip()
        prov = chunk["provenance"]
        assert prov.get("reference")
        assert prov.get("url") or prov.get("doi") or prov.get("source_file")
        url = prov.get("url")
        if url:
            assert "localhost" not in url.lower()


def test_api_serves_curated_without_synthetic_flag() -> None:
    settings = Settings(
        data_dir=REPO_ROOT / "data",
        trial_files="curated/trials.json",
        document_chunks_file="curated/document_chunks.json",
        include_synthetic=False,
        explainer="offline",
    )
    client = TestClient(build_app(build_container(settings)))
    trials = client.get("/api/v1/trials").json()
    ids = {t["id"] for t in trials}
    assert ids
    assert all(not tid.startswith("SYN-") for tid in ids)
    assert all(t["investigation"] == "BASS-II" for t in trials)
    assert all(t["is_synthetic"] is False for t in trials)

    sample = client.get(f"/api/v1/trials/{trials[0]['id']}")
    assert sample.status_code == 200
    body = sample.json()
    assert body["provenance"]["reference"]
