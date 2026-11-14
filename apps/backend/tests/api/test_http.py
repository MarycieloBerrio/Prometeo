from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prometeo.bootstrap.api import build_app
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.settings import Settings

DATA_DIR = Path(__file__).resolve().parents[4] / "data"


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        data_dir=DATA_DIR,
        trial_files="fixtures/synthetic_trials.json",
        include_synthetic=True,
        explainer="offline",
    )
    return TestClient(build_app(build_container(settings)))


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_lists_and_filters_trials(client: TestClient) -> None:
    ids = {t["id"] for t in client.get("/api/v1/trials").json()}
    assert {"SYN-001", "SYN-002", "SYN-003", "SYN-004"} <= ids
    cylinders = client.get("/api/v1/trials", params={"geometry": "cylinder"}).json()
    assert [t["id"] for t in cylinders] == ["SYN-003"]


def test_unknown_trial_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/trials/NOPE").status_code == 404


def test_comparison_withholds_deltas_for_incompatible_trials(client: TestClient) -> None:
    body = {"trial_a": "SYN-001", "trial_b": "SYN-003", "varied": ["flow_speed"]}
    res = client.post("/api/v1/comparisons", json=body).json()
    assert res["level"] == "not_comparable"
    assert res["deltas"] == []
    assert res["withheld_reason"]


def test_comparison_computes_delta_for_compatible_trials(client: TestClient) -> None:
    body = {"trial_a": "SYN-001", "trial_b": "SYN-002", "varied": ["flow_speed"]}
    res = client.post("/api/v1/comparisons", json=body).json()
    assert res["level"] == "directly_comparable"
    assert res["deltas"][0]["difference"]["value"] == pytest.approx(0.5)


def test_coverage_map_marks_cells(client: TestClient) -> None:
    res = client.get("/api/v1/coverage").json()
    assert any(c["has_evidence"] for c in res["cells"])
    assert any(not c["has_evidence"] for c in res["cells"])


def test_assistant_refuses_on_synthetic_data(client: TestClient) -> None:
    body = client.post(
        "/api/v1/assistant/ask", json={"question": "Effect of flow on spread?"}
    ).json()
    assert body["tier"] == "insufficient"
    assert body["answer"] is None
