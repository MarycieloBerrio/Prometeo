"""Abstention battery: the assistant must refuse, without calling the model, whenever the
recorded evidence does not support a conclusion — and a refusal must never carry a number.

All trials and documents are TEST FIXTURES (see tests/assistant/fakes.py), not NASA data.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from prometeo.application.use_cases.ask_research_assistant import AssistantAnswer
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import (
    DataQuality,
    FlowDirection,
    Fuel,
    Investigation,
    Measurement,
    Provenance,
    ThermalRegime,
    Trial,
)
from prometeo.domain.shared.quantity import Quantity
from tests.assistant.fakes import NUMBER, ScriptedExplainer, ask, doc
from tests.factories import TEST_PROV, make_trial


def _with_fsr(trial_id: str, value: float, **overrides: object) -> Trial:
    m = Measurement("flame_spread_rate", Quantity(value, "mm/s"), DataQuality.MEASURED, TEST_PROV)
    return make_trial(trial_id, results=(m,), **overrides)


def _assert_refused(answer: AssistantAnswer, spy: ScriptedExplainer) -> None:
    assert answer.tier is EvidenceTier.INSUFFICIENT
    assert answer.explanation is None
    assert answer.refusal_reason
    assert spy.calls == []  # the model is never consulted
    reason = answer.refusal_reason
    assert "will not extrapolate" in reason or reason.startswith("Out of scope")


# ---- 1-3: zero data, synthetic-only, documents-only ----------------------------------------


def test_refuses_with_zero_trials_and_says_absence_is_not_safety() -> None:
    answer, spy = ask([])
    _assert_refused(answer, spy)
    assert answer.computed_facts == ()
    assert "No curated trial matches" in answer.refusal_reason
    assert "not evidence of safety" in answer.refusal_reason


def test_refusal_names_the_missing_conditions() -> None:
    answer, spy = ask(
        [_with_fsr("A", 1.0), _with_fsr("B", 2.0)],
        criteria=TrialFilter(material="cotton", flow_direction=FlowDirection.OPPOSED),
    )
    _assert_refused(answer, spy)
    assert "material=cotton" in answer.refusal_reason
    assert "flow_direction=opposed" in answer.refusal_reason


def test_refuses_on_synthetic_only_data_and_never_prints_synthetic_values() -> None:
    synthetic = [
        _with_fsr("SYN-A", 4.321, investigation=Investigation.SYNTHETIC),
        _with_fsr("SYN-B", 8.765, investigation=Investigation.SYNTHETIC),
    ]
    answer, spy = ask(synthetic, criteria=TrialFilter(include_synthetic=True))
    _assert_refused(answer, spy)
    assert "synthetic" in answer.refusal_reason.lower()
    assert answer.computed_facts == ()
    blob = answer.refusal_reason + " ".join(answer.limitations)
    assert "4.321" not in blob and "8.765" not in blob


def test_documents_alone_never_become_a_quantitative_answer() -> None:
    context = doc("ctx-1", "TEST FIXTURE: a spread rate of 9.87 mm/s was reported at 3.21 cm/s.")
    answer, spy = ask([], docs=[context])
    _assert_refused(answer, spy)
    assert answer.documents == (context,)  # still shown, as context
    assert "context only" in answer.refusal_reason
    assert "9.87" not in answer.refusal_reason and "3.21" not in answer.refusal_reason
    assert answer.computed_facts == ()


# ---- 4-8: coverage and quality gates --------------------------------------------------------


def test_refuses_with_a_single_usable_trial() -> None:
    answer, spy = ask([_with_fsr("A", 1.0)])
    _assert_refused(answer, spy)
    assert "1 of 1 matching trials are usable" in answer.refusal_reason


def test_synthetic_trial_does_not_complete_a_real_pair() -> None:
    trials = [
        _with_fsr("A", 1.0),
        _with_fsr("SYN-B", 6.543, investigation=Investigation.SYNTHETIC),
    ]
    answer, spy = ask(trials, criteria=TrialFilter(include_synthetic=True))
    _assert_refused(answer, spy)
    assert all("SYN-B" not in f for f in answer.computed_facts)
    assert "6.543" not in " ".join(answer.computed_facts)


def test_refuses_when_requested_metric_is_not_recorded() -> None:
    trials = [make_trial("A", results=()), make_trial("B", results=())]
    answer, spy = ask(trials)
    _assert_refused(answer, spy)
    assert "No 'flame_spread_rate' result recorded" in answer.refusal_reason


def test_unreviewed_extracted_values_are_neither_evidence_nor_facts() -> None:
    extracted = Measurement(
        "flame_spread_rate", Quantity(7.777, "mm/s"), DataQuality.EXTRACTED, TEST_PROV
    )
    trials = [make_trial("A", results=(extracted,)), make_trial("B", results=(extracted,))]
    answer, spy = ask(trials)
    _assert_refused(answer, spy)
    assert "7.777" not in " ".join(answer.computed_facts)
    assert "extracted" in answer.refusal_reason


def test_values_without_traceable_source_are_refused() -> None:
    untraceable = Provenance(reference="somebody said so")  # no doi, url or source_file
    m = Measurement("flame_spread_rate", Quantity(1.0, "mm/s"), DataQuality.MEASURED, untraceable)
    trials = [make_trial("A", results=(m,)), make_trial("B", results=(m,))]
    answer, spy = ask(trials)
    _assert_refused(answer, spy)
    assert "traceable source" in answer.refusal_reason


def test_refuses_when_oxygen_range_is_asked_but_oxygen_was_not_recorded() -> None:
    trials = [_with_fsr("A", 1.0, oxygen=None), _with_fsr("B", 2.0, oxygen=None)]
    answer, spy = ask(
        trials, criteria=TrialFilter(oxygen_min=Quantity(15, "%"), oxygen_max=Quantity(19, "%"))
    )
    _assert_refused(answer, spy)  # unknown O2 never silently satisfies a numeric filter
    assert "oxygen_min=15 %" in answer.refusal_reason


# ---- 9-11: incompatible comparisons (Physics Validator) ------------------------------------


@pytest.mark.parametrize(
    ("label", "overrides"),
    [
        ("different fuel", {"fuel": Fuel("other-material")}),
        (
            "thin vs thick",
            {"geometry": replace(make_trial().geometry, thermal_regime=ThermalRegime.THICK)},
        ),
        (
            "opposed vs concurrent",
            {"ventilation": replace(make_trial().ventilation, direction=FlowDirection.OPPOSED)},
        ),
    ],
)
def test_refuses_to_conclude_across_incompatible_trials(
    label: str, overrides: dict[str, object]
) -> None:
    answer, spy = ask([_with_fsr("A", 1.0), _with_fsr("B", 2.0, **overrides)])
    _assert_refused(answer, spy)
    assert "Physics Validator" in answer.refusal_reason, label
    # Each value may still be listed as an observation, but no interpretation is produced.
    assert len(answer.computed_facts) == 2


# ---- 12: questions outside Prometeo's scope -------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Is this test-material safe to use aboard a crewed spacecraft?",
        "Can Prometeo certify the material for flight?",
        "What is the % confidence that the sample ignites?",
        "What is the probability of a fire at these conditions?",
        "How would flame spread change on the lunar surface?",
        "Will the material behave the same in Martian gravity?",
        "Predict the flame spread rate at 12% oxygen.",
        "What would happen in a full-scale cabin fire?",
        "How would a new composite material burn under these flows?",
    ],
)
def test_refuses_out_of_scope_questions_even_with_good_evidence(question: str) -> None:
    good = [_with_fsr("A", 1.0), _with_fsr("B", 2.0, ventilation=make_trial().ventilation)]
    answer, spy = ask(good, question)
    _assert_refused(answer, spy)
    assert answer.refusal_reason.startswith("Out of scope")


@pytest.mark.parametrize(
    "question",
    [
        "How does flame spread over a solid change with ventilation speed in microgravity?",
        "Does flame spread rate peak at an intermediate opposed flow?",
        "At what oxygen percentage was spread observed?",
        "What does the fire safety literature say about thin fuels?",
    ],
)
def test_in_scope_questions_are_not_blocked_by_the_scope_guard(question: str) -> None:
    faster = replace(make_trial().ventilation, speed=Quantity(10, "cm/s"))
    trials = [_with_fsr("A", 1.0), _with_fsr("B", 2.0, ventilation=faster)]
    answer, spy = ask(trials, question)
    assert answer.refusal_reason is None
    assert len(spy.calls) == 1


def test_refusal_reasons_carry_only_counts_never_measured_values() -> None:
    trials = [_with_fsr("A", 3.14159), make_trial("B", results=())]
    answer, _ = ask(trials, docs=[doc("d", "TEST FIXTURE 2.71828 mm/s")])
    numbers = set(NUMBER.findall(answer.refusal_reason))
    assert numbers <= {"0", "1", "2"}  # trial/document counts and the coverage minimum
