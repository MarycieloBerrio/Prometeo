"""HTTP contract of the model picker and the source-document endpoint. Offline only."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from prometeo.adapters.outbound.persistence.source_file_store import (
    NoSourceFiles,
    PostgresSourceFileStore,
)
from prometeo.application.ports.outbound import ExplainerModel, SourceFile
from prometeo.bootstrap.api import build_app
from prometeo.bootstrap.container import Container, build_container
from prometeo.bootstrap.settings import Settings

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
QUESTION = {"question": "Effect of flow on spread?"}


def _container(**overrides: Any) -> Container:
    settings = Settings(
        data_dir=DATA_DIR,
        trial_files="fixtures/synthetic_trials.json",
        include_synthetic=True,
        explainer="offline",
        document_store="json",  # never depend on a local .env pointing at Postgres
    )
    return build_container(settings, **overrides)


def test_no_model_is_offered_with_the_deterministic_explainer() -> None:
    client = TestClient(build_app(_container()))
    assert client.get("/api/v1/assistant/models").json() == {"default": None, "models": []}
    # A model sent anyway is ignored rather than rejected: there is nothing to choose.
    body = {**QUESTION, "model": "claude-opus-5-5"}
    assert client.post("/api/v1/assistant/ask", json=body).status_code == 200


def test_offered_models_are_listed_default_first_and_others_are_rejected() -> None:
    offered = (
        ExplainerModel("test-default", "Test default", "TEST FIXTURE"),
        ExplainerModel("test-other", "Test other", "TEST FIXTURE"),
    )
    client = TestClient(build_app(replace(_container(), explainer_models=offered)))
    listed = client.get("/api/v1/assistant/models").json()
    assert listed["default"] == "test-default"
    assert [m["id"] for m in listed["models"]] == ["test-default", "test-other"]

    ok = client.post("/api/v1/assistant/ask", json={**QUESTION, "model": "test-other"})
    assert ok.status_code == 200
    bad = client.post("/api/v1/assistant/ask", json={**QUESTION, "model": "not-offered"})
    assert bad.status_code == 422 and "not-offered" in bad.json()["detail"]


class _OneFile:
    def __init__(self, file: SourceFile) -> None:
        self._file = file

    def locate(self, chunk_id: str) -> SourceFile | None:
        return self._file if chunk_id == "known-chunk" else None


def test_source_document_is_served_inline_or_404(tmp_path: Path) -> None:
    pdf = tmp_path / "TEST FIXTURE report.pdf"
    pdf.write_bytes(b"%PDF-1.4 TEST FIXTURE")
    store = _OneFile(SourceFile(pdf, "application/pdf", pdf.name))
    client = TestClient(build_app(_container(source_files=store)))

    found = client.get("/api/v1/documents/known-chunk/file")
    assert found.status_code == 200
    assert found.content == b"%PDF-1.4 TEST FIXTURE"
    assert found.headers["content-type"] == "application/pdf"
    assert found.headers["content-disposition"].startswith("inline")

    missing = client.get("/api/v1/documents/other-chunk/file")
    assert missing.status_code == 404 and "No local source file" in missing.json()["detail"]


def test_json_document_store_has_no_source_files() -> None:
    assert NoSourceFiles().locate("anything") is None
    client = TestClient(build_app(_container()))
    assert client.get("/api/v1/documents/anything/file").status_code == 404


class _FakeConnection:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> _FakeConnection:
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


def _store(monkeypatch: pytest.MonkeyPatch, raw_dir: Path, row: tuple[Any, ...] | None) -> (
    PostgresSourceFileStore
):
    monkeypatch.setattr(psycopg, "connect", lambda dsn: _FakeConnection(row))
    return PostgresSourceFileStore("postgresql://test.invalid/none", raw_dir)


def test_recorded_file_is_resolved_inside_the_raw_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = tmp_path / "raw"
    (raw / "psi").mkdir(parents=True)
    (raw / "psi" / "report.pdf").write_bytes(b"%PDF")
    found = _store(monkeypatch, raw, ("psi/report.pdf", "application/pdf", None)).locate("c")
    assert found is not None
    assert found.path == (raw / "psi" / "report.pdf").resolve()
    assert found.media_type == "application/pdf" and found.file_name == "report.pdf"


@pytest.mark.parametrize(
    "row",
    [
        None,  # unknown chunk, or a chunk with no asset
        ("", "application/pdf", "x.pdf"),  # asset never downloaded
        ("psi/not-downloaded.pdf", "application/pdf", "x.pdf"),  # raw file absent locally
        ("../secret.pdf", "application/pdf", "secret.pdf"),  # escapes the raw folder
    ],
)
def test_missing_or_outside_files_are_never_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: tuple[Any, ...] | None
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (tmp_path / "secret.pdf").write_bytes(b"%PDF outside the raw folder")
    assert _store(monkeypatch, raw, row).locate("c") is None
