"""EvidenceRank unit tests — tiers stay interpretable; no confidence percentages."""

from prometeo.domain.evidence.ranking import (
    MIN_TRIALS_FOR_COMPARISON,
    EvidenceTier,
    Level,
    assess_trial,
    overall_tier,
)
from prometeo.domain.experiments.filters import TrialFilter
from tests.factories import make_trial


def test_min_trials_for_comparison_is_two() -> None:
    assert MIN_TRIALS_FOR_COMPARISON == 2


def test_overall_tier_insufficient_with_single_usable_trial() -> None:
    """Comparative coverage rule: one usable trial → insufficient (by design today)."""
    trial = make_trial("A")
    assessment = assess_trial(trial, TrialFilter(material="test-material"), "flame_spread_rate")
    assert assessment.tier is EvidenceTier.DIRECT
    assert overall_tier([assessment]) is EvidenceTier.INSUFFICIENT


def test_overall_tier_direct_with_two_direct_assessments() -> None:
    a = assess_trial(make_trial("A"), TrialFilter(material="test-material"), "flame_spread_rate")
    b = assess_trial(make_trial("B"), TrialFilter(material="test-material"), "flame_spread_rate")
    assert overall_tier([a, b]) is EvidenceTier.DIRECT


def test_synthetic_trial_is_low_quality_insufficient() -> None:
    from prometeo.domain.experiments.model import Investigation

    trial = make_trial("SYN", investigation=Investigation.SYNTHETIC)
    assessment = assess_trial(trial, TrialFilter(), None)
    assert assessment.quality is Level.LOW
    assert assessment.tier is EvidenceTier.INSUFFICIENT
    assert any("Synthetic" in r for r in assessment.reasons)
