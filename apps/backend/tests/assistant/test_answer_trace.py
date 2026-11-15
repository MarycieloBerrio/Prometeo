"""What the answer tells the reader about its own basis: which trials were interpreted, which
conditions were uncontrolled (and whether they differ or are simply unknown), whether a trend
runs along one physical sample, and which document text the model actually received.

All trials and documents are TEST FIXTURES, not NASA data.
"""

from __future__ import annotations

from dataclasses import replace

from prometeo.adapters.inbound.http.schemas import ask_out
from prometeo.application.ports.outbound import DocumentChunk
from prometeo.application.use_cases.ask_research_assistant import DOCUMENT_LIMIT
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.model import DataQuality, Fuel, Measurement, Trial
from prometeo.domain.shared.quantity import Quantity
from tests.assistant.fakes import ask, doc
from tests.factories import TEST_PROV, make_trial


def _pair(**overrides: object) -> list[Trial]:
    """Two comparable TEST trials that differ only in flow speed (5 vs 10 cm/s)."""
    slow = make_trial("TEST-SLOW", **overrides)
    fast_vent = replace(slow.ventilation, speed=Quantity(10, "cm/s"))
    m = Measurement("flame_spread_rate", Quantity(2.5, "mm/s"), DataQuality.MEASURED, TEST_PROV)
    return [slow, make_trial("TEST-FAST", ventilation=fast_vent, results=(m,), **overrides)]


def _set_limitation(limitations: tuple[str, ...]) -> str:
    return next(lim for lim in limitations if lim.startswith("Comparable set 1"))


# ---- one physical sample is a series, not replicates ---------------------------------------


def test_condition_points_on_one_sample_are_flagged_as_a_series_not_replicates() -> None:
    answer, spy = ask(_pair(sample_id="TEST-S1"))
    note = next(lim for lim in answer.limitations if lim.startswith("Same physical sample"))
    assert "sample TEST-S1 [TEST-FAST, TEST-SLOW]" in note
    assert "not independent replicates" in note
    assert note in spy.calls[0].limitations  # the explainer is told, too
    assert answer.explanation is not None and note in answer.explanation.text


def test_trials_on_different_or_unrecorded_samples_carry_no_same_sample_note() -> None:
    slow, fast = _pair()
    for trials in (
        [replace(slow, sample_id="TEST-S1"), replace(fast, sample_id="TEST-S2")],
        [slow, fast],  # sample_id unknown: nothing is assumed
    ):
        answer, _ = ask(trials)
        assert not any("Same physical sample" in lim for lim in answer.limitations)


# ---- differ vs unknown ---------------------------------------------------------------------


def test_unknown_conditions_are_reported_as_unknown_not_as_differing() -> None:
    answer, _ = ask(_pair(pressure=None))
    text = _set_limitation(answer.limitations)
    assert "these conditions differ: flow_speed." in text
    assert "unknown for at least one trial: pressure;" in text
    assert "differ or are unknown" not in text


def test_fully_recorded_conditions_list_no_unknowns() -> None:
    text = _set_limitation(ask(_pair())[0].limitations)
    assert "these conditions differ: flow_speed." in text
    assert "unknown for at least one trial" not in text


def test_same_sample_notice_alone_is_not_reported_as_a_flow_difference() -> None:
    # Identical recorded conditions on one sample: the validator's same-sample notice is
    # filed under flow_speed, but nothing differs.
    twins = [make_trial("TEST-A", sample_id="TEST-S1"), make_trial("TEST-B", sample_id="TEST-S1")]
    answer, _ = ask(twins)
    text = _set_limitation(answer.limitations)
    assert "differ" not in text and "unknown" not in text
    assert any(lim.startswith("Same physical sample") for lim in answer.limitations)


# ---- which trials the interpretation used --------------------------------------------------


def test_trial_without_a_comparable_counterpart_is_marked_as_not_interpreted() -> None:
    other = make_trial("TEST-OTHER", fuel=Fuel("other-test-material"))
    answer, _ = ask([*_pair(), other])
    assert answer.interpreted_trial_ids == {"TEST-SLOW", "TEST-FAST"}

    out = ask_out(answer)
    used = {a.trial_id: a.in_interpretation for a in out.assessments}
    assert used == {"TEST-SLOW": True, "TEST-FAST": True, "TEST-OTHER": False}
    # Its own tier is untouched: it rates the trial alone, not its use in the answer.
    assert next(a for a in out.assessments if a.trial_id == "TEST-OTHER").tier == "direct"


def test_a_refusal_interprets_no_trial() -> None:
    answer, _ = ask([make_trial("TEST-ONLY")])
    assert answer.tier is EvidenceTier.INSUFFICIENT
    assert answer.interpreted_trial_ids == frozenset()
    assert [a.in_interpretation for a in ask_out(answer).assessments] == [False]


# ---- documents -----------------------------------------------------------------------------

BOILERPLATE = (
    "TEST FIXTURE: microgravity removes buoyant convection, so oxygen reaches the flame by "
    "diffusion and forced ventilation, which changes flame shape and spread."
)


def _distinct_docs(count: int) -> list[DocumentChunk]:
    return [
        doc(f"ctx-{i:02d}", "TEST FIXTURE " + " ".join(f"topic{i}word{j}" for j in range(8)))
        for i in range(count)
    ]


def test_repeated_boilerplate_is_collapsed_to_its_best_ranked_copy() -> None:
    docs = [
        doc("first", BOILERPLATE),
        doc("copy", BOILERPLATE + " The same paragraph, reprinted in an interim report."),
        doc("other", "TEST FIXTURE: rods were ignited at the downstream end of the duct."),
    ]
    answer, spy = ask(_pair(), docs=docs)
    assert [d.id for d in answer.documents] == ["first", "other"]
    assert [d.id for d in spy.calls[0].documents] == ["first", "other"]


def test_duplicates_do_not_take_slots_from_distinct_documents() -> None:
    distinct = _distinct_docs(DOCUMENT_LIMIT)
    copies = [doc(f"copy-{i}", BOILERPLATE) for i in range(4)]
    answer, _ = ask(_pair(), docs=[*copies, *distinct])
    ids = [d.id for d in answer.documents]
    assert len(ids) == DOCUMENT_LIMIT
    assert ids[0] == "copy-0" and sum(i.startswith("copy-") for i in ids) == 1


def test_at_most_the_document_limit_is_returned() -> None:
    answer, _ = ask(_pair(), docs=_distinct_docs(DOCUMENT_LIMIT + 5))
    assert len(answer.documents) == DOCUMENT_LIMIT


def test_api_returns_the_full_chunk_the_model_received() -> None:
    long_text = "TEST FIXTURE: " + "background sentence. " * 60 + "The decisive statement."
    assert len(long_text) > 1000
    answer, spy = ask(_pair(), docs=[doc("long", long_text)])
    assert ask_out(answer).documents[0].excerpt == long_text == spy.calls[0].documents[0].text


def test_document_limitation_does_not_name_a_retrieval_method_it_may_not_use() -> None:
    answer, _ = ask(_pair(), docs=[doc("ctx", BOILERPLATE)])
    note = next(lim for lim in answer.limitations if lim.startswith("Document excerpts"))
    assert "word overlap" not in note and "text similarity" in note
