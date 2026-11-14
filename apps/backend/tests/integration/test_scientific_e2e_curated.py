"""End-to-end scientific validation against curated NASA BASS-II evidence.

Uses an explicit Settings → container → TestClient path with
`curated/trials.json` and `include_synthetic=False`. Does not call localhost
or load `fixtures/synthetic_trials.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import (
    CURATED_TRIALS,
    EXPECTED_CURATED_IDS,
    FLAMEVISION_INDEX,
    FLAMEVISION_MANIFEST,
    REPO_ROOT,
)


def test_01_curated_dataset_snapshot() -> None:
    raw = json.loads(CURATED_TRIALS.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 7
    ids = {row["id"] for row in raw}
    assert ids == EXPECTED_CURATED_IDS
    assert all(row.get("investigation") != "SYNTHETIC" for row in raw)
    assert all(not row.get("is_synthetic", False) for row in raw)
    # Six rod condition points share two physical samples — not six replicates.
    sample_ids = {row.get("sample_id") for row in raw if row["id"].startswith("BASS-II-B")}
    assert sample_ids == {"B16", "B19"}
    for row in raw:
        for media in row.get("media") or []:
            uri = str(media.get("uri") or "")
            assert "example.com" not in uri
            assert "localhost" not in uri
            assert not uri.startswith("file:")


def test_02_api_health(curated_client: TestClient) -> None:
    res = curated_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_03_explorer_lists_seven_bass2_trials(curated_client: TestClient) -> None:
    res = curated_client.get("/api/v1/trials")
    assert res.status_code == 200
    trials = res.json()
    assert isinstance(trials, list)
    assert len(trials) == 7
    ids = {t["id"] for t in trials}
    assert ids == EXPECTED_CURATED_IDS
    assert all(not t["is_synthetic"] for t in trials)
    assert all(t["investigation"] == "BASS-II" for t in trials)


def test_03b_trial_sheet_b16_vg167(curated_client: TestClient) -> None:
    res = curated_client.get("/api/v1/trials/BASS-II-B16-Vg167")
    assert res.status_code == 200
    trial = res.json()
    assert trial["investigation"] == "BASS-II"
    assert trial["sample_id"] == "B16"
    assert trial["material"] == "PMMA"
    assert trial["flow_direction"] == "opposed"
    assert trial["oxygen"]["value"] == pytest.approx(18.2)
    assert trial["oxygen"]["unit"] == "%"
    assert trial["flow_speed"]["value"] == pytest.approx(1.67)
    assert trial["flow_speed"]["unit"] == "cm/s"
    assert trial["pressure"] is None
    assert trial["media"] == []
    fsr = next(m for m in trial["results"] if m["name"] == "flame_spread_rate")
    assert fsr["value"]["value"] == pytest.approx(0.0762)
    assert fsr["value"]["unit"] == "mm/s"
    assert fsr["quality"] == "measured"
    # SCHEMA LIMITATION (documented): cylinders expose diameter via thickness.
    assert trial["geometry"] == "cylinder"
    assert trial["thickness"] is not None
    assert trial["thickness"]["value"] == pytest.approx(6.4)
    assert trial["thickness"]["unit"] == "mm"


def test_04a_comparison_b16_flow_partial_withholds_deltas(curated_client: TestClient) -> None:
    body = {
        "trial_a": "BASS-II-B16-Vg755",
        "trial_b": "BASS-II-B16-Vg167",
        "varied": ["flow_speed"],
        "metrics": ["flame_spread_rate"],
    }
    res = curated_client.post("/api/v1/comparisons", json=body)
    assert res.status_code == 200
    out = res.json()
    assert out["level"] == "partially_comparable"
    assert out["deltas"] == []
    assert out["withheld_reason"]
    assert any(
        i["variable"] == "pressure" and i["severity"] == "warning" for i in out["issues"]
    )
    assert {t["id"] for t in out["trials"]} == {
        "BASS-II-B16-Vg755",
        "BASS-II-B16-Vg167",
    }
    # Measured values remain visible on each trial even when causal Δ is withheld.
    for trial in out["trials"]:
        fsr = next(m for m in trial["results"] if m["name"] == "flame_spread_rate")
        assert fsr["quality"] == "measured"
        assert fsr["value"]["unit"] == "mm/s"


def test_04b_comparison_b16_b19_oxygen_partial(curated_client: TestClient) -> None:
    body = {
        "trial_a": "BASS-II-B16-Vg167",
        "trial_b": "BASS-II-B19-Vg167",
        "varied": ["oxygen"],
        "metrics": ["flame_spread_rate"],
    }
    res = curated_client.post("/api/v1/comparisons", json=body)
    assert res.status_code == 200
    out = res.json()
    assert out["level"] == "partially_comparable"
    assert out["deltas"] == []
    assert out["withheld_reason"]
    assert any(i["variable"] == "pressure" for i in out["issues"])


def test_04c_comparison_film_not_comparable(curated_client: TestClient) -> None:
    body = {
        "trial_a": "BASS-II-B16-Vg167",
        "trial_b": "BASS-II-FILM-100um-SR-extinction-context",
        "varied": ["flow_speed"],
        "metrics": ["flame_spread_rate"],
    }
    res = curated_client.post("/api/v1/comparisons", json=body)
    assert res.status_code == 200
    out = res.json()
    assert out["level"] == "not_comparable"
    assert out["deltas"] == []
    assert out["withheld_reason"]


def test_05_coverage_map_has_evidence_and_gaps(curated_client: TestClient) -> None:
    res = curated_client.get("/api/v1/coverage")
    assert res.status_code == 200
    cov = res.json()
    assert cov["cells"]
    assert any(c["has_evidence"] for c in cov["cells"])
    # Empty cells must remain empty — absence ≠ safety.
    assert any(not c["has_evidence"] for c in cov["cells"])
    placed = {tid for c in cov["cells"] for tid in c["trial_ids"]}
    assert placed & EXPECTED_CURATED_IDS


def test_06_assistant_demo_question_uses_evidence(curated_client: TestClient) -> None:
    body = {
        "question": (
            "How does flame spread over a solid change with ventilation speed "
            "in microgravity for BASS-II PMMA rods?"
        ),
        "material": "PMMA",
        "geometry": "cylinder",
        "flow_direction": "opposed",
        "metric": "flame_spread_rate",
    }
    res = curated_client.post("/api/v1/assistant/ask", json=body)
    assert res.status_code == 200
    out = res.json()
    assert out["tier"] in {"direct", "partial", "insufficient"}
    # Offline explainer must not invent numeric claims outside the packet.
    if out["tier"] == "insufficient":
        assert out["answer"] is None
    else:
        assert out["answer"]
        assert out["computed_facts"] or out["assessments"] or out["cited_sources"]
        assert "SYN-" not in (out["answer"] or "")


def test_07_flamevision_artifacts_unvalidated_px() -> None:
    index = json.loads(FLAMEVISION_INDEX.read_text(encoding="utf-8"))
    assert index["runs"]
    run = index["runs"][0]
    assert run["key"] == "psi25-test-b9"
    assert run["prometeo_trial_id"] is None
    assert run["validation_status"] == "UNVALIDATED"
    assert run["position_unit"] == "px"
    assert run["rate_unit"] == "px/s"

    manifest = json.loads(FLAMEVISION_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["validation_status"] == "UNVALIDATED"
    assert manifest["position_unit"] == "px"
    assert manifest["rate_unit"] == "px/s"
    assert manifest["prometeo_trial_id"] is None
    assert "reaction" not in manifest.get("feature", "").lower() or "luminous" in manifest[
        "feature"
    ].lower()
    assert Path(FLAMEVISION_MANIFEST).parent.joinpath("track.csv").is_file()
    assert Path(FLAMEVISION_MANIFEST).parent.joinpath("curve.png").is_file()


def test_08_validate_data_cli_ok() -> None:
    import shutil
    import subprocess

    uv = shutil.which("uv")
    assert uv, "uv is required to run prometeo validate-data"
    proc = subprocess.run(
        [uv, "run", "prometeo", "validate-data"],
        cwd=REPO_ROOT / "apps" / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "OK:" in proc.stdout
