from dataclasses import replace

from prometeo.application.ports.outbound import DocumentChunk, EvidencePacket, Explanation
from prometeo.application.use_cases.ask_research_assistant import (
    AskResearchAssistant,
    AssistantAnswer,
    AssistantQuery,
    comparable_groups,
    out_of_scope_reason,
)
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import (
    DataQuality,
    FlowDirection,
    Fuel,
    Measurement,
    Trial,
)
from prometeo.domain.shared.quantity import Quantity
from tests.factories import TEST_PROV, make_trial


class FakeRepo:
    def __init__(self, trials: list[Trial]) -> None:
        self._t = {t.id: t for t in trials}

    def get(self, trial_id: str) -> Trial | None:
        return self._t.get(trial_id)

    def search(self, criteria: TrialFilter) -> list[Trial]:
        return [t for t in self._t.values() if criteria.matches(t)]

    def list_all(self) -> list[Trial]:
        return list(self._t.values())


class NoDocs:
    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]:
        return []


class SpyExplainer:
    def __init__(self) -> None:
        self.calls: list[EvidencePacket] = []

    def explain(self, packet: EvidencePacket) -> Explanation:
        self.calls.append(packet)
        return Explanation("ok", (), "spy")


def _ask(trials: list[Trial], spy: SpyExplainer, metric: str | None = "flame_spread_rate") -> (
    AssistantAnswer
):
    use_case = AskResearchAssistant(FakeRepo(trials), NoDocs(), spy)
    return use_case.execute(AssistantQuery("How does flow affect spread?", TrialFilter(), metric))


def test_refuses_without_calling_llm_when_evidence_insufficient() -> None:
    spy = SpyExplainer()
    answer = _ask([make_trial("A")], spy)  # a single trial cannot support a comparison
    assert answer.tier is EvidenceTier.INSUFFICIENT
    assert answer.explanation is None
    assert answer.refusal_reason
    assert spy.calls == []


def test_explains_when_two_traceable_measured_trials_match() -> None:
    spy = SpyExplainer()
    answer = _ask([make_trial("A"), make_trial("B")], spy)
    assert answer.tier is EvidenceTier.DIRECT
    assert len(spy.calls) == 1
    assert len(spy.calls[0].computed_facts) == 2


def test_facts_carry_value_unit_quality_source_and_conditions() -> None:
    spy = SpyExplainer()
    answer = _ask([make_trial("A"), make_trial("B")], spy)
    fact = answer.computed_facts[0]
    assert fact.startswith("[A] BASS-II · flame_spread_rate = 1 mm/s (measured)")
    assert f"source: {TEST_PROV.reference}" in fact
    assert "O2 21 %, flow 5 cm/s (concurrent)" in fact


def test_unknown_conditions_are_shown_as_unknown_never_zero() -> None:
    spy = SpyExplainer()
    no_speed = replace(make_trial().ventilation, speed=None)
    answer = _ask([make_trial("A", oxygen=None, ventilation=no_speed), make_trial("B")], spy)
    fact = next(f for f in answer.computed_facts if f.startswith("[A]"))
    assert "O2 unknown" in fact and "flow unknown" in fact


def test_only_comparable_trials_reach_the_explainer() -> None:
    spy = SpyExplainer()
    other_fuel = make_trial("C", fuel=Fuel("other"))
    answer = _ask([make_trial("A"), make_trial("B"), other_fuel], spy)
    assert [t.id for t in spy.calls[0].trials] == ["A", "B"]
    assert all(not f.startswith("[C]") for f in answer.computed_facts)
    assert any("Excluded from the interpretation" in lim and "C" in lim for lim in
               answer.limitations)


def test_derived_values_without_method_are_not_reported_as_facts() -> None:
    derived = Measurement(
        "flame_spread_rate", Quantity(4.444, "mm/s"), DataQuality.DERIVED, TEST_PROV
    )
    spy = SpyExplainer()
    answer = _ask([make_trial("A"), make_trial("B", results=(derived,))], spy)
    assert "4.444" not in " ".join(answer.computed_facts)


def test_without_a_metric_only_reviewed_results_of_usable_trials_are_printed() -> None:
    # A usable trial may carry other results; unreviewed ones must not leak as facts.
    extracted = Measurement(
        "heat_release_rate", Quantity(3.333, "W"), DataQuality.EXTRACTED, TEST_PROV
    )
    trial_a = make_trial("A")
    trial_a = replace(trial_a, results=(*trial_a.results, extracted))
    spy = SpyExplainer()
    answer = _ask([trial_a, make_trial("B")], spy, metric=None)
    facts = " ".join(answer.computed_facts)
    assert "flame_spread_rate = 1 mm/s (measured)" in facts
    assert "3.333" not in facts and "heat_release_rate" not in facts


def test_synthetic_results_are_never_reportable_even_if_ranking_changes() -> None:
    # Defense in depth: today EvidenceRank already rejects synthetic trials; this guard
    # keeps their values out of facts if that rule is ever relaxed.
    from prometeo.application.use_cases.ask_research_assistant import _reportable
    from prometeo.domain.experiments.model import Investigation

    synthetic = make_trial("SYN", investigation=Investigation.SYNTHETIC)
    assert _reportable(synthetic, None) == []
    assert _reportable(synthetic, "flame_spread_rate") == []


def test_comparable_groups_never_bridge_through_unknown_direction() -> None:
    unknown = replace(make_trial().ventilation, direction=FlowDirection.UNKNOWN)
    opposed = replace(make_trial().ventilation, direction=FlowDirection.OPPOSED)
    trials = [
        make_trial("A-unknown", ventilation=unknown),
        make_trial("B-concurrent"),
        make_trial("C-opposed", ventilation=opposed),
    ]
    for group in comparable_groups(trials):
        directions = {t.ventilation.direction for t in group} - {FlowDirection.UNKNOWN}
        assert len(directions) <= 1


def test_scope_guard_does_not_trip_on_fire_safety_or_oxygen_percentage() -> None:
    assert out_of_scope_reason("What does fire safety research say about PMMA?") is None
    assert out_of_scope_reason("At what oxygen percentage did spread stop?") is None
    assert out_of_scope_reason("Is PMMA safe?") is not None
