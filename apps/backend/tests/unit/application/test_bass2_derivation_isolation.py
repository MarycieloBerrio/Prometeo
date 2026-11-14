"""Post-merge guards: BASS-II flow derivation must not contaminate curated evidence.

Uses a fake PSI catalog and a temporary ``data/processed`` destination. The real
``data/curated`` tree is read-only (hashed before/after); never used as ``--out``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.derive_bass2_flow import DeriveBass2FlowSpeeds
from prometeo.bootstrap.api import build_app
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.safe_output import atomic_write_text, resolve_processed_json_output
from prometeo.bootstrap.settings import Settings
from prometeo.domain.physics.compatibility import Comparability, Variable
from tests.unit.application.test_derive_bass2_flow import FakeCatalog

REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_DIR = REPO_ROOT / "data"
CURATED_TRIALS = DATA_DIR / "curated" / "trials.json"
CURATED_CHUNKS = DATA_DIR / "curated" / "document_chunks.json"

# Published Link et al. Table S1 values already asserted elsewhere — frozen here so a
# derivation worksheet cannot silently redefine what Explorer/Compare serve.
B16_VF_MM_S = {
    "BASS-II-B16-Vg755": 0.0678,
    "BASS-II-B16-Vg167": 0.0762,
    "BASS-II-B16-Vg072": 0.0568,
}
B16_VG_CM_S = {
    "BASS-II-B16-Vg755": 7.55,
    "BASS-II-B16-Vg167": 1.67,
    "BASS-II-B16-Vg072": 0.72,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus_digests() -> dict[str, str]:
    paths = [
        CURATED_TRIALS,
        CURATED_CHUNKS,
        *sorted((DATA_DIR / "curated").glob("*.json")),
    ]
    # Unique paths only.
    return {str(p.resolve()): _sha256(p) for p in dict.fromkeys(paths)}


def _write_fake_worksheet(tmp_path: Path) -> Path:
    """Run derivation against invented CSV; write only under a temp processed/."""
    data_dir = tmp_path / "data"
    processed = data_dir / "processed"
    processed.mkdir(parents=True)
    report = DeriveBass2FlowSpeeds(FakeCatalog()).execute()
    target = resolve_processed_json_output(
        processed / "bass2_flow_speeds.json",
        data_dir=data_dir,
    )
    payload = {
        "status": "DERIVED ESTIMATES FOR HUMAN REVIEW. Not curated evidence.",
        "quality": "derived",
        "method": report.method,
        "tests": [{"test": t.test_label, "kind": t.derivation.kind.value} for t in report.tests],
    }
    atomic_write_text(target, json.dumps(payload, indent=2) + "\n")
    return target


def test_derivation_worksheet_does_not_change_curated_hashes(tmp_path: Path) -> None:
    before = _corpus_digests()
    assert len(before) >= 2

    target = _write_fake_worksheet(tmp_path)
    assert target.is_file()
    assert "1.0066" in json.loads(target.read_text(encoding="utf-8"))["method"]

    after = _corpus_digests()
    assert after == before
    # Worksheet lives only in the temp tree — not under real data/curated.
    assert CURATED_TRIALS.resolve() not in {p.resolve() for p in target.parents}


def test_curated_repository_still_serves_seven_link_trials_after_derivation(
    tmp_path: Path,
) -> None:
    _write_fake_worksheet(tmp_path)
    repo = JsonTrialRepository([CURATED_TRIALS])
    trials = repo.list_all()
    assert len(trials) == 7
    assert sum(t.is_synthetic for t in trials) == 0
    for trial_id, vf in B16_VF_MM_S.items():
        trial = repo.get(trial_id)
        assert trial is not None
        assert trial.ventilation is not None
        assert trial.ventilation.speed.value == pytest.approx(B16_VG_CM_S[trial_id])
        m = trial.measurement("flame_spread_rate")
        assert m is not None
        assert m.quality.value == "measured"
        assert m.value.value == pytest.approx(vf)


def test_compare_b16_still_partial_without_using_derivation_worksheet(
    tmp_path: Path,
) -> None:
    worksheet = _write_fake_worksheet(tmp_path)
    # CompareTrials talks only to the trial repository — worksheet path must stay unused.
    compare = CompareTrials(JsonTrialRepository([CURATED_TRIALS]))
    result = compare.execute(
        "BASS-II-B16-Vg755",
        "BASS-II-B16-Vg167",
        frozenset({Variable.FLOW_SPEED}),
        ["flame_spread_rate"],
    )
    assert result.compatibility.level is Comparability.PARTIAL
    assert result.deltas == ()
    assert worksheet.is_file()
    assert "derived" in worksheet.read_text(encoding="utf-8").lower()


def test_http_explorer_smoke_on_curated_unaffected_by_temp_worksheet(
    tmp_path: Path,
) -> None:
    _write_fake_worksheet(tmp_path)
    settings = Settings(
        data_dir=DATA_DIR,
        trial_files="curated/trials.json",
        include_synthetic=False,
        explainer="offline",
        document_store="json",
    )
    client = TestClient(build_app(build_container(settings)))
    trials = client.get("/api/v1/trials").json()
    assert len(trials) == 7
    by_id = {t["id"]: t for t in trials}
    assert by_id["BASS-II-B16-Vg167"]["flow_speed"]["value"] == pytest.approx(1.67)
    fsr = next(r for r in by_id["BASS-II-B16-Vg167"]["results"] if r["name"] == "flame_spread_rate")
    assert fsr["value"]["value"] == pytest.approx(0.0762)
    assert fsr["quality"] == "measured"

    body = {
        "trial_a": "BASS-II-B16-Vg755",
        "trial_b": "BASS-II-B16-Vg167",
        "varied": ["flow_speed"],
    }
    comparison = client.post("/api/v1/comparisons", json=body).json()
    assert comparison["level"] == "partially_comparable"
    assert comparison["deltas"] == []


def test_observational_chart_source_has_no_fan_calibration_import() -> None:
    """Frontend chart must keep reading Trial DTOs only — no derivation module coupling."""
    chart = (
        REPO_ROOT
        / "apps"
        / "frontend"
        / "src"
        / "components"
        / "compare"
        / "ObservationalSpreadChart.tsx"
    )
    text = chart.read_text(encoding="utf-8")
    assert "fan_calibration" not in text
    assert "bass2_flow" not in text
    assert "1.0066" not in text
    assert "derived" not in text.lower() or "no fitted" in text.lower()
