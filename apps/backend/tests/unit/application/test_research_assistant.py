from prometeo.application.ports.outbound import DocumentChunk, EvidencePacket, Explanation
from prometeo.application.use_cases.ask_research_assistant import (
    AskResearchAssistant,
    AssistantAnswer,
    AssistantQuery,
)
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Trial
from tests.factories import make_trial


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


def _ask(trials: list[Trial], spy: SpyExplainer) -> AssistantAnswer:
    use_case = AskResearchAssistant(FakeRepo(trials), NoDocs(), spy)
    return use_case.execute(
        AssistantQuery("How does flow affect spread?", TrialFilter(), "flame_spread_rate")
    )


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
