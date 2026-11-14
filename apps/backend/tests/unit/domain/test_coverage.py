from prometeo.domain.evidence.coverage import build_coverage_map
from tests.factories import make_trial


def test_trials_land_in_cells_and_empty_cells_have_no_evidence() -> None:
    cmap = build_coverage_map([make_trial("A")], [0.15, 0.20, 0.25], [0, 4, 8])
    filled = [c for c in cmap.cells if c.has_evidence]
    assert len(cmap.cells) == 4
    assert [c.trial_ids for c in filled] == [("A",)]
    assert filled[0].oxygen_range == (0.20, 0.25)
    assert filled[0].flow_range == (4, 8)


def test_trials_without_conditions_are_reported_unplaced() -> None:
    cmap = build_coverage_map([make_trial("A", oxygen=None)], [0.15, 0.25], [0, 10])
    assert cmap.unplaced_trial_ids == ("A",)
