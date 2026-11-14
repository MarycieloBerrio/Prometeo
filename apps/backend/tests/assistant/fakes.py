"""Test doubles for the Research Assistant evaluation battery.

Every value here is INVENTED for tests. Trials come from `tests.factories.make_trial`, whose
provenance is "unit-test fixture" at example.invalid; documents below are labelled TEST
FIXTURE. Nothing in this package is NASA data or may be shipped as such.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from prometeo.application.ports.outbound import DocumentChunk, EvidencePacket, Explanation
from prometeo.application.use_cases.ask_research_assistant import (
    AskResearchAssistant,
    AssistantAnswer,
    AssistantQuery,
)
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Provenance, Trial

TEST_DOC_PROV = Provenance(
    reference="TEST FIXTURE document — not a NASA source", url="https://example.invalid/doc"
)

# Numbers anywhere in a string (used to prove no quantitative claim leaks into a refusal).
NUMBER = re.compile(r"\d+(?:\.\d+)?")


class FakeRepo:
    def __init__(self, trials: Sequence[Trial]) -> None:
        self._t = {t.id: t for t in trials}

    def get(self, trial_id: str) -> Trial | None:
        return self._t.get(trial_id)

    def search(self, criteria: TrialFilter) -> list[Trial]:
        return [t for t in self._t.values() if criteria.matches(t)]

    def list_all(self) -> list[Trial]:
        return list(self._t.values())


class StaticDocs:
    def __init__(self, docs: Sequence[DocumentChunk] = ()) -> None:
        self._docs = list(docs)

    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]:
        return self._docs[:limit]


class ScriptedExplainer:
    """Plays back a fixed model output and records every packet it was given."""

    def __init__(
        self, text: str = "Interpretation.", sources: Sequence[str] = (), model: str = "scripted"
    ) -> None:
        self.text, self.sources, self.model = text, tuple(sources), model
        self.calls: list[EvidencePacket] = []

    def explain(self, packet: EvidencePacket) -> Explanation:
        self.calls.append(packet)
        return Explanation(self.text, self.sources, self.model)


def doc(chunk_id: str, text: str, prov: Provenance = TEST_DOC_PROV) -> DocumentChunk:
    return DocumentChunk(chunk_id, text, prov, score=1.0)


def ask(
    trials: Sequence[Trial],
    question: str = "How does flow speed affect flame spread?",
    *,
    criteria: TrialFilter | None = None,
    metric: str | None = "flame_spread_rate",
    docs: Sequence[DocumentChunk] = (),
    explainer: ScriptedExplainer | None = None,
) -> tuple[AssistantAnswer, ScriptedExplainer]:
    spy = explainer or ScriptedExplainer()
    use_case = AskResearchAssistant(FakeRepo(trials), StaticDocs(docs), spy)
    answer = use_case.execute(AssistantQuery(question, criteria or TrialFilter(), metric))
    return answer, spy
