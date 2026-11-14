"""Hardened BASS-II curation semantics: Table S1 values, condition points, unknowns."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.adapters.outbound.persistence.trial_codec import trial_from_json
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.bootstrap.api import build_app
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.settings import Settings
from prometeo.domain.experiments.model import GeometryType, ThermalRegime
from prometeo.domain.physics.compatibility import Variable, assess_compatibility

REPO_ROOT = Path(__file__).resolve().parents[4]
CURATED_TRIALS = REPO_ROOT / "data" / "curated" / "trials.json"
CURATED_CHUNKS = REPO_ROOT / "data" / "curated" / "document_chunks.json"
MANIFEST = REPO_ROOT / "data" / "sources" / "bass2-manifest.json"
VALIDATE_STAGING = REPO_ROOT / "tools" / "nasa_ingest" / "validate_staging.py"
EXPORT_CURATED = REPO_ROOT / "tools" / "nasa_ingest" / "export_curated_trials.py"

# Table S1 (Link et al. 2018 supplement): Vf x 10^3 values under the cm/s x 10^3 interpretation.
# Conversion: mm/s = (table_value) * 0.01. Re-verified from local PDF 2026-11-14.
# Right-column PDF header prints "(mm/s)" but magnitudes match left cm/s x 10^3 / Table S2.
EXPECTED_B16_B19: dict[str, dict[str, float | str]] = {
    "BASS-II-B16-Vg755": {
        "sample_id": "B16",
        "oxygen_pct": 18.2,
        "vg_cm_s": 7.55,
        "vf_x1000": 6.78,
        "vf_mm_s": 0.0678,
        "dt_s": 72,
    },
    "BASS-II-B16-Vg167": {
        "sample_id": "B16",
        "oxygen_pct": 18.2,
        "vg_cm_s": 1.67,
        "vf_x1000": 7.62,
        "vf_mm_s": 0.0762,
        "dt_s": 139,
    },
    "BASS-II-B16-Vg083": {
        "sample_id": "B16",
        "oxygen_pct": 18.2,
        "vg_cm_s": 0.83,
        "vf_x1000": 6.99,
        "vf_mm_s": 0.0699,
        "dt_s": 198,
    },
    "BASS-II-B16-Vg072": {
        "sample_id": "B16",
        "oxygen_pct": 18.2,
        "vg_cm_s": 0.72,
        "vf_x1000": 5.68,
        "vf_mm_s": 0.0568,
        "dt_s": 170,
    },
    "BASS-II-B19-Vg755": {
        "sample_id": "B19",
        "oxygen_pct": 17.5,
        "vg_cm_s": 7.55,
        "vf_x1000": 4.69,
        "vf_mm_s": 0.0469,
        "dt_s": 67,
    },
    "BASS-II-B19-Vg167": {
        "sample_id": "B19",
        "oxygen_pct": 17.5,
        "vg_cm_s": 1.67,
        "vf_x1000": 6.52,
        "vf_mm_s": 0.0652,
        "dt_s": 128,
    },
}


@pytest.fixture(scope="module")
def curated_raw() -> list[dict]:
    return json.loads(CURATED_TRIALS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(curated_raw: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in curated_raw}


def test_exactly_seven_real_records(curated_raw: list[dict]) -> None:
    assert len(curated_raw) == 7
    assert len({r["id"] for r in curated_raw}) == 7
    assert all(r["investigation"] == "BASS-II" for r in curated_raw)
    assert all(not str(r["id"]).startswith("SYN") for r in curated_raw)


def test_condition_points_share_physical_sample_ids(by_id: dict[str, dict]) -> None:
    b16 = [by_id[i] for i in EXPECTED_B16_B19 if EXPECTED_B16_B19[i]["sample_id"] == "B16"]
    b19 = [by_id[i] for i in EXPECTED_B16_B19 if EXPECTED_B16_B19[i]["sample_id"] == "B19"]
    assert len(b16) == 4
    assert len(b19) == 2
    assert {r["sample_id"] for r in b16} == {"B16"}
    assert {r["sample_id"] for r in b19} == {"B19"}
    # Distinct trial ids, fewer physical samples than condition points.
    assert len({r["id"] for r in b16 + b19}) == 6
    assert len({r["sample_id"] for r in b16 + b19}) == 2
    for r in b16 + b19:
        tags = set(r.get("tags") or [])
        assert "condition-point" in tags
        assert "not-independent-replicate" in tags
        assert f"physical-sample-{r['sample_id']}" in tags
        assert "SEMANTICS:" in (r.get("notes") or "")


def test_table_s1_values_and_unit_conversion(by_id: dict[str, dict]) -> None:
    for tid, exp in EXPECTED_B16_B19.items():
        raw = by_id[tid]
        assert raw["sample_id"] == exp["sample_id"]
        assert raw["oxygen"]["value"] == pytest.approx(float(exp["oxygen_pct"]))
        assert raw["oxygen"]["unit"] == "%"
        assert raw["ventilation"]["speed"]["value"] == pytest.approx(float(exp["vg_cm_s"]))
        assert raw["ventilation"]["speed"]["unit"] == "cm/s"
        assert raw["ventilation"]["direction"] == "opposed"
        meas = raw["results"][0]
        assert meas["name"] == "flame_spread_rate"
        assert meas["quality"] == "measured"
        assert meas["value"]["unit"] == "mm/s"
        assert meas["value"]["value"] == pytest.approx(float(exp["vf_mm_s"]))
        # Unit conversion invariant from declared Table S1 Vf x 10^3 (cm/s).
        assert float(exp["vf_x1000"]) * 0.01 == pytest.approx(float(exp["vf_mm_s"]))
        assert meas["value"]["value"] == pytest.approx(float(exp["vf_x1000"]) * 0.01)
        assert str(exp["dt_s"]) in (meas["provenance"].get("page") or "")


def test_rod_pressure_and_film_unknowns_are_absent(by_id: dict[str, dict]) -> None:
    for tid in EXPECTED_B16_B19:
        raw = by_id[tid]
        assert "pressure" not in raw or raw.get("pressure") is None
        trial = trial_from_json(raw)
        assert trial.pressure is None

    film = by_id["BASS-II-FILM-100um-SR-extinction-context"]
    assert "oxygen" not in film or film.get("oxygen") is None
    assert film.get("ventilation", {}).get("speed") is None
    assert "pressure" not in film or film.get("pressure") is None
    ft = trial_from_json(film)
    assert ft.oxygen is None
    assert ft.ventilation.speed is None
    assert ft.pressure is None
    assert ft.results[0].value.value == pytest.approx(2.2)
    assert ft.results[0].value.unit == "mm/s"


def test_cylinder_thickness_field_is_diameter_not_film(by_id: dict[str, dict]) -> None:
    """Schema freeze: geometry.thickness holds diameter for rods — must not be treated as film."""
    rod = trial_from_json(by_id["BASS-II-B16-Vg167"])
    film = trial_from_json(by_id["BASS-II-FILM-100um-SR-extinction-context"])
    assert rod.geometry.type is GeometryType.CYLINDER
    assert film.geometry.type is GeometryType.SHEET
    assert rod.geometry.thermal_regime is ThermalRegime.THICK
    assert film.geometry.thermal_regime is ThermalRegime.THIN
    assert rod.geometry.thickness is not None and film.geometry.thickness is not None
    # Same numeric "thickness" slot would be scientifically meaningless across regimes.
    assert rod.geometry.thickness.to("mm").value == pytest.approx(6.4)
    assert film.geometry.thickness.to("mm").value == pytest.approx(0.1)
    assert "geometry-thickness-means-diameter" in set(by_id["BASS-II-B16-Vg167"].get("tags") or [])
    assert "DIAMETER" in (by_id["BASS-II-B16-Vg167"].get("notes") or "")


def test_no_fabricated_media_uris(curated_raw: list[dict]) -> None:
    for raw in curated_raw:
        assert raw.get("media") == []
        blob = json.dumps(raw).lower()
        assert ".mp4" not in blob
        assert "localhost" not in blob


def test_document_chunks_distinguish_nasa_tm_peer_review_and_psi() -> None:
    chunks = json.loads(CURATED_CHUNKS.read_text(encoding="utf-8"))
    assert len(chunks) == 8
    by_id = {c["id"]: c for c in chunks}
    assert "nasa.gov" in by_id["bass2-tm-overview-limitations"]["provenance"]["url"]
    assert "10.1038/s41598-017-18398-4" in (
        by_id["bass2-link2018-nonmonotonic-opposed"]["provenance"].get("doi") or ""
    )
    assert "psi.nasa.gov" in by_id["bass2-psi25-access-and-scope"]["provenance"]["url"]
    assert "not NASA evidence" in by_id["bass2-evidence-absence-not-safety"]["text"]
    # Internal curation rule chunk must not claim experimental NASA measurement numbers.
    assert "2.2 mm/s" not in by_id["bass2-evidence-absence-not-safety"]["text"]


def test_manifest_lists_gaps_and_sources() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest["curated_trial_ids"]) == {
        *EXPECTED_B16_B19.keys(),
        "BASS-II-FILM-100um-SR-extinction-context",
    }
    assert any("concurrent" in g.lower() for g in manifest["evidence_gaps"])
    src_ids = {s["id"] for s in manifest["sources"]}
    assert {"psi-25", "ntrs-tm-20210011385", "nature-link-2018"} <= src_ids
    link = next(s for s in manifest["sources"] if s["id"] == "nature-link-2018")
    assert link["used_for_curated_numbers"] is True
    psi = next(s for s in manifest["sources"] if s["id"] == "psi-25")
    assert psi["used_for_curated_numbers"] is False


def test_export_refuses_overwrite_without_force(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    staging.write_text(CURATED_TRIALS.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out.json"
    out.write_text("[]\n", encoding="utf-8")
    refused = subprocess.run(
        [sys.executable, str(EXPORT_CURATED), str(staging), str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 3
    assert "REFUSED" in refused.stderr
    assert out.read_text(encoding="utf-8") == "[]\n"


def test_validate_staging_cli_passes_curated() -> None:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE_STAGING), str(CURATED_TRIALS)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "OK:" in proc.stdout


def test_compare_behavior_observed_for_handoff_to_daniel() -> None:
    """Dataset semantics under Daniel's hardened Physics Validator (PR #7).

    Curated BASS-II condition points omit pressure. Unknown controlled variables
    are not matches, so these pairs stay PARTIAL and causal deltas stay withheld
    until pressure (and other controls) are curated. Does not edit Daniel's code.
    """
    repo = JsonTrialRepository([CURATED_TRIALS])
    compare = CompareTrials(repo)

    flow = compare.execute(
        "BASS-II-B16-Vg755",
        "BASS-II-B16-Vg167",
        frozenset({Variable.FLOW_SPEED}),
        ["flame_spread_rate"],
    )
    assert flow.compatibility.level.value == "partially_comparable"
    assert flow.deltas == ()
    assert flow.withheld_reason
    assert any(
        i.variable is Variable.PRESSURE and i.severity.value == "warning"
        for i in flow.compatibility.issues
    )

    ox = compare.execute(
        "BASS-II-B16-Vg167",
        "BASS-II-B19-Vg167",
        frozenset({Variable.OXYGEN}),
        ["flame_spread_rate"],
    )
    assert ox.compatibility.level.value == "partially_comparable"
    assert ox.deltas == ()
    assert ox.withheld_reason
    assert any(i.variable is Variable.PRESSURE for i in ox.compatibility.issues)

    film = compare.execute(
        "BASS-II-B16-Vg167",
        "BASS-II-FILM-100um-SR-extinction-context",
        frozenset({Variable.FLOW_SPEED}),
        ["flame_spread_rate"],
    )
    assert film.compatibility.level.value == "not_comparable"
    assert film.deltas == ()
    assert film.withheld_reason

    # Dual-null pressure is a WARNING, not a silent match.
    a = repo.get("BASS-II-B16-Vg755")
    b = repo.get("BASS-II-B16-Vg167")
    assert a is not None and b is not None
    report = assess_compatibility(a, b, frozenset({Variable.FLOW_SPEED}))
    assert any(
        i.variable is Variable.PRESSURE and i.severity.value == "warning"
        for i in report.issues
    )


def test_api_lists_empty_media_not_fake_player() -> None:
    settings = Settings(
        data_dir=REPO_ROOT / "data",
        trial_files="curated/trials.json",
        include_synthetic=False,
        explainer="offline",
    )
    client = TestClient(build_app(build_container(settings)))
    trial = client.get("/api/v1/trials/BASS-II-B16-Vg167").json()
    assert trial["media"] == []
    assert trial["sample_id"] == "B16"
    assert trial["pressure"] is None
