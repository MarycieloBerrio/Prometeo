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
        document_store="json",  # never depend on a local .env pointing at Postgres
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


def test_cfd_simulations_list_and_field(client: TestClient) -> None:
    sims = client.get("/api/v1/cfd/simulations").json()
    assert len(sims) >= 4
    ids = {s["simulation_id"] for s in sims}
    assert "CFD-B16-Vg072" in ids
    assert all(s["result_kind"] == "numerical_simulation" for s in sims)
    linked = client.get(
        "/api/v1/cfd/simulations", params={"trial_id": "BASS-II-B16-Vg072"}
    ).json()
    assert len(linked) == 1
    assert linked[0]["reference_trial_id"] == "BASS-II-B16-Vg072"
    field = client.get("/api/v1/cfd/simulations/CFD-B16-Vg072/field").json()
    assert field["simulation_id"] == "CFD-B16-Vg072"
    assert len(field["points"]) > 0
    interp = client.get("/api/v1/cfd/simulations/CFD-B16-Vg072/interpretation").json()
    assert "cannot_conclude" in interp
    joined = " ".join(interp["cannot_conclude"]).lower()
    assert "non-reactive" in joined or "cannot" in joined
    assert client.get("/api/v1/cfd/simulations/CFD-MISSING").status_code == 404


def test_cfd_simulation_exposes_numeric_geometry(client: TestClient) -> None:
    sim = client.get("/api/v1/cfd/simulations/CFD-B16-Vg072").json()
    geo = sim["geometry"]
    assert geo is not None
    assert geo["rod_radius_m"] == 0.0032
    assert geo["duct_outer_radius_m"] == 0.038
    assert geo["domain_length_m"] == 0.12
    assert geo["mesh_resolution"] == [24, 1, 80]


def test_cfd_interpretation_wording_stays_within_evidence(client: TestClient) -> None:
    interp = client.get("/api/v1/cfd/simulations/CFD-B16-Vg755/interpretation").json()
    assert "appear to peak" in interp["question"]
    measured = " ".join(interp["nasa_measured"])
    assert "not a statistically demonstrated peak" in measured
    assert "not independent ignitions" in measured
    assert "10³·Vf" in measured and "0.0568 mm/s" in measured
    literature = " ".join(interp["literature_mechanisms"])
    # Da is quoted exactly as Link et al. write it, and its trend is NOT asserted.
    assert "Da = t_chem / t_flow" in literature
    assert "does not evaluate Da" in literature
    cannot = " ".join(interp["cannot_conclude"]).lower()
    assert "causality" in cannot and "cannot demonstrate" in cannot
