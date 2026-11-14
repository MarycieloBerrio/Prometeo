"""Ground-truth evaluation cases for the Research Assistant.

Each case states what a scientifically honest assistant MUST do with the given evidence.
Values are TEST FIXTURES built with `make_trial` (provenance "unit-test fixture",
example.invalid); they only exercise the pipeline and are never NASA results.

Cases (also summarized in docs/assistant-evaluation-alejandro.md):

* flow-variation: 2 trials, same fuel/geometry, flow 5 vs 10 cm/s -> answer (direct).
* missing-oxygen: O2 not recorded but an O2 range is asked -> refuse, names the filter.
* incompatible-comparison: same flow, different fuel -> refuse (Physics Validator).
* missing-source: measured values without a traceable source -> refuse.
* citation-control: 2 comparable trials + a document; the model cites an invented NASA
  report -> answer, invented citation removed.
* unsupported-question: good evidence, asks for a lunar prediction -> refuse (scope).
* mixed-quality: 2 measured + 1 extracted + 1 synthetic -> answer from the 2 only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace

import pytest

from prometeo.application.use_cases.ask_research_assistant import AssistantAnswer
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import (
    DataQuality,
    Fuel,
    Investigation,
    Measurement,
    Provenance,
    Trial,
)
from prometeo.domain.shared.quantity import Quantity
from tests.assistant.fakes import ScriptedExplainer, ask, doc
from tests.factories import TEST_PROV, make_trial

FAKE_REF = "Invented et al., NASA/TP-2099 (does not exist)"


def _fsr(
    value: float, quality: DataQuality = DataQuality.MEASURED, prov: Provenance = TEST_PROV
) -> tuple[Measurement, ...]:
    return (Measurement("flame_spread_rate", Quantity(value, "mm/s"), quality, prov),)


def _at_flow(trial_id: str, speed: float, value: float, **kw: object) -> Trial:
    base = make_trial(trial_id)
    vent = replace(base.ventilation, speed=Quantity(speed, "cm/s"))
    return make_trial(trial_id, ventilation=vent, results=_fsr(value), **kw)


@dataclass(frozen=True)
class Case:
    name: str
    trials: list[Trial]
    question: str = "How does flame spread change with flow speed?"
    criteria: TrialFilter = field(default_factory=TrialFilter)
    model_text: str = "[GT-A] and [GT-B] differ in flow speed."
    model_sources: tuple[str, ...] = ()
    expect_tier: EvidenceTier = EvidenceTier.INSUFFICIENT
    expect_model_called: bool = False
    facts_contain: tuple[str, ...] = ()
    nowhere: tuple[str, ...] = ()  # strings that must not appear in any output field
    check: Callable[[AssistantAnswer], None] | None = None


def _refusal_mentions(text: str) -> Callable[[AssistantAnswer], None]:
    def check(a: AssistantAnswer) -> None:
        assert a.refusal_reason is not None and text in a.refusal_reason

    return check


def _citation_removed(a: AssistantAnswer) -> None:
    assert a.explanation is not None
    assert FAKE_REF not in a.explanation.cited_sources
    assert "TEST FIXTURE document — not a NASA source" in a.explanation.cited_sources


CASES = [
    Case(
        "flow-variation",
        [_at_flow("GT-A", 5, 1.0), _at_flow("GT-B", 10, 2.0)],
        expect_tier=EvidenceTier.DIRECT,
        expect_model_called=True,
        facts_contain=("flame_spread_rate = 1 mm/s", "flame_spread_rate = 2 mm/s", "flow 10 cm/s"),
    ),
    Case(
        "missing-oxygen",
        [_at_flow("GT-A", 5, 1.0, oxygen=None), _at_flow("GT-B", 10, 2.0, oxygen=None)],
        criteria=TrialFilter(oxygen_min=Quantity(16, "%")),
        check=_refusal_mentions("oxygen_min=16 %"),
    ),
    Case(
        "incompatible-comparison",
        [_at_flow("GT-A", 5, 1.0), _at_flow("GT-B", 5, 3.0, fuel=Fuel("another-fuel"))],
        check=_refusal_mentions("Physics Validator"),
    ),
    Case(
        "missing-source",
        [
            make_trial("GT-A", results=_fsr(1.0, prov=Provenance("hearsay"))),
            make_trial("GT-B", results=_fsr(2.0, prov=Provenance("hearsay"))),
        ],
        check=_refusal_mentions("traceable source"),
    ),
    Case(
        "citation-control",
        [_at_flow("GT-A", 5, 1.0), _at_flow("GT-B", 10, 2.0)],
        model_sources=("TEST FIXTURE document — not a NASA source", FAKE_REF),
        expect_tier=EvidenceTier.DIRECT,
        expect_model_called=True,
        nowhere=(FAKE_REF,),
        check=_citation_removed,
    ),
    Case(
        "unsupported-question",
        [_at_flow("GT-A", 5, 1.0), _at_flow("GT-B", 10, 2.0)],
        question="Predict flame spread for this material on the Moon.",
        check=_refusal_mentions("Out of scope"),
    ),
    Case(
        "mixed-quality",
        [
            _at_flow("GT-A", 5, 1.0),
            _at_flow("GT-B", 10, 2.0),
            make_trial("GT-X", results=_fsr(5.555, DataQuality.EXTRACTED)),
            make_trial("SYN-GT", investigation=Investigation.SYNTHETIC, results=_fsr(6.666)),
        ],
        criteria=TrialFilter(include_synthetic=True),
        expect_tier=EvidenceTier.DIRECT,
        expect_model_called=True,
        facts_contain=("[GT-A]", "[GT-B]"),
        nowhere=("5.555", "6.666", "[GT-X]", "[SYN-GT]"),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_ground_truth(case: Case) -> None:
    explainer = ScriptedExplainer(case.model_text, case.model_sources, model="scripted-model")
    context = doc("gt-doc", "TEST FIXTURE: flame spread depends on flow speed.")
    answer, spy = ask(
        case.trials, case.question, criteria=case.criteria, docs=[context], explainer=explainer
    )

    assert answer.tier is case.expect_tier
    assert bool(spy.calls) is case.expect_model_called
    if case.expect_tier is EvidenceTier.INSUFFICIENT:
        assert answer.explanation is None and answer.refusal_reason
    else:
        assert answer.explanation is not None and answer.refusal_reason is None

    facts = " ".join(answer.computed_facts)
    for needle in case.facts_contain:
        assert needle in facts
    rendered = " ".join(
        [
            facts,
            " ".join(answer.limitations),
            answer.refusal_reason or "",
            answer.explanation.text if answer.explanation else "",
            " ".join(answer.explanation.cited_sources) if answer.explanation else "",
            " ".join(t.id for t in spy.calls[0].trials) if spy.calls else "",
        ]
    )
    for needle in case.nowhere:
        assert needle not in rendered
    if case.check:
        case.check(answer)
