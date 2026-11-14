"""End-to-end tests for tools/flamevision/track_video.py on code-generated videos."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from .conftest import FPS, Scene, VideoFactory

pytest.importorskip("cv2", reason="needs `uv sync --extra vision`")

TOOL = Path(__file__).resolve().parents[4] / "tools" / "flamevision" / "track_video.py"
SPEED_PX_S = 3.0 * FPS


@pytest.fixture(scope="module")
def cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("flamevision_track_video", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_uncalibrated_run_reports_pixels_only(
    cli: ModuleType, make_video: VideoFactory, tmp_path: Path
) -> None:
    video = make_video(Scene())
    before = Path(video).read_bytes()
    out = tmp_path / "out"

    code = cli.main(
        [
            video,
            "--out-dir",
            str(out),
            "--roi",
            "0,30,320,60",
            "--trial-key",
            "synthetic-clip",
            "--keyframes",
            "4",
            "--overlay",
        ]
    )

    assert code == 0
    assert Path(video).read_bytes() == before  # the source is never modified
    doc = json.loads((out / "track.json").read_text(encoding="utf-8"))
    assert doc["schema"] == "prometeo.flamevision.track/v1"
    assert doc["feature"] == "luminous_leading_edge"
    assert "not the reaction front" in doc["feature_note"]
    assert doc["verdict"] == "SUITABLE"
    assert doc["validation"]["status"] == "UNVALIDATED"
    assert doc["physical"] is None
    assert doc["units"]["edge_px"] == "px" and doc["units"]["rate"] == "px/s"
    assert "position_mm" not in doc["units"]
    assert doc["diagnostics"]["advance_px_per_s"] == pytest.approx(SPEED_PX_S, rel=0.02)
    assert doc["method"]["config"]["roi"] == {"x": 0, "y": 30, "width": 320, "height": 60}
    assert doc["method"]["opencv_version"]
    assert len(doc["source"]["sha256"]) == 64
    assert doc["source"]["prometeo_trial_id"] is None  # never invented
    assert doc["source"]["url"] is None

    rows = list(csv.DictReader((out / "track.csv").open(encoding="utf-8")))
    assert len(rows) == 60 == len(doc["observations"])
    assert "position_mm" not in rows[0]
    assert rows[0]["status"] == "detected"

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["position_unit"] == "px" and manifest["rate_unit"] == "px/s"
    assert manifest["validation_status"] == "UNVALIDATED"
    for name in manifest["files"]:
        assert (out / name).is_file(), name
    assert {"curve.png", "keyframes.jpg", "overlay.mp4"} <= set(manifest["files"])


def test_runs_are_reproducible(cli: ModuleType, make_video: VideoFactory, tmp_path: Path) -> None:
    video = make_video(Scene(frames=20))
    for name in ("a", "b"):
        cli.main([video, "--out-dir", str(tmp_path / name)])
    for artifact in ("track.json", "track.csv"):
        assert (tmp_path / "a" / artifact).read_bytes() == (tmp_path / "b" / artifact).read_bytes()


def test_calibrated_run_validates_against_a_reference(
    cli: ModuleType, make_video: VideoFactory, tmp_path: Path
) -> None:
    # 90 px/s * 0.1 mm/px = 9 mm/s. The "reference" is this test's own ground truth.
    common = [
        make_video(Scene()),
        "--mm-per-pixel",
        "0.1",
        "--calibration-source",
        "synthetic test scale",
        "--reference-source",
        "synthetic ground truth",
    ]

    cli.main([*common, "--out-dir", str(tmp_path / "ok"), "--reference-mm-s", "9.0"])
    doc = json.loads((tmp_path / "ok" / "track.json").read_text(encoding="utf-8"))
    velocity = doc["physical"]["spread_velocity"]
    assert velocity["unit"] == "mm/s" and velocity["quality"] == "derived"
    assert velocity["value"] == pytest.approx(9.0, rel=0.02)
    assert doc["validation"]["status"] == "VALIDATED"
    assert doc["validation"]["absolute_error"]["value"] == pytest.approx(0.0, abs=0.2)
    assert abs(doc["validation"]["relative_error_pct"]) < 2.0
    assert doc["physical"]["calibration"]["source"] == "synthetic test scale"
    rows = list(csv.DictReader((tmp_path / "ok" / "track.csv").open(encoding="utf-8")))
    assert "position_mm" in rows[0]

    cli.main([*common, "--out-dir", str(tmp_path / "bad"), "--reference-mm-s", "5.0"])
    doc = json.loads((tmp_path / "bad" / "track.json").read_text(encoding="utf-8"))
    assert doc["validation"]["status"] == "REJECTED"
    assert doc["validation"]["relative_error_pct"] == pytest.approx(80.0, rel=0.05)


def test_unsuitable_video_gets_no_velocity_even_when_calibrated(
    cli: ModuleType, make_video: VideoFactory, tmp_path: Path
) -> None:
    video = make_video(Scene(level=255))  # saturated
    cli.main(
        [
            video,
            "--out-dir",
            str(tmp_path),
            "--mm-per-pixel",
            "0.1",
            "--calibration-source",
            "synthetic test scale",
        ]
    )
    doc = json.loads((tmp_path / "track.json").read_text(encoding="utf-8"))

    assert doc["verdict"] == "NOT_SUITABLE"
    assert doc["physical"]["spread_velocity"] is None
    assert doc["validation"]["status"] == "UNVALIDATED"


@pytest.mark.parametrize(
    "extra",
    [
        ["--mm-per-pixel", "0.1"],  # scale without a source
        ["--calibration-source", "ruler"],  # source without a scale
        ["--mm-per-pixel", "0", "--calibration-source", "ruler"],
        ["--reference-mm-s", "2.0", "--reference-source", "paper"],  # reference, no scale
        ["--mm-per-pixel", "0.1", "--calibration-source", "ruler", "--reference-mm-s", "2.0"],
        ["--fps", "0"],
        ["--roi", "1,2,3"],
        ["--roi", "900,0,10,10"],
    ],
)
def test_bad_arguments_fail_with_a_clear_error(
    cli: ModuleType, make_video: VideoFactory, tmp_path: Path, extra: list[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main([make_video(Scene(frames=5)), "--out-dir", str(tmp_path / "x"), *extra])
    assert str(excinfo.value).startswith("error:")
    assert not (tmp_path / "x" / "track.json").exists()


def test_missing_video_fails_with_a_clear_error(cli: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="video not found"):
        cli.main([str(tmp_path / "nope.mp4"), "--out-dir", str(tmp_path / "x")])
