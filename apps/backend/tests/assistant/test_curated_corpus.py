"""Invariants that must hold on WHATEVER is in data/curated — empty today on main, the
BASS-II corpus once the data PR lands. These tests do not assert specific NASA values (the
data team owns those); they assert that the assistant stays honest on real data:

* every document chunk loads with a provenance reference;
* the demo question is either refused or answered with numbers that all come from the
  audited evidence, citations that all resolve to the packet, and no synthetic records;
* out-of-scope questions are refused on real data too.

To run against another corpus (e.g. a data branch checked out elsewhere), set the
environment variable PROMETEO_EVAL_DATA_DIR to a folder containing curated/trials.json and
curated/document_chunks.json.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from prometeo.adapters.outbound.retrieval.keyword_retriever import KeywordRetriever
from prometeo.application.ports.outbound import EvidencePacket
from prometeo.application.use_cases.ask_research_assistant import (
    AssistantQuery,
    allowed_sources,
    unsupported_numbers,
)
from prometeo.bootstrap.container import build_container
from prometeo.bootstrap.settings import Settings
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import FlowDirection

REPO_DATA = Path(__file__).resolve().parents[4] / "data"
DATA_DIR = Path(os.environ.get("PROMETEO_EVAL_DATA_DIR") or REPO_DATA)

DEMO = "How does flame spread over a solid change with ventilation speed in microgravity?"


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(data_dir=DATA_DIR, explainer="offline", include_synthetic=False)


def test_every_curated_chunk_is_indexable(settings: Settings) -> None:
    retriever = KeywordRetriever(settings.data_dir / settings.document_chunks_file)
    assert retriever.rejected == ()


@pytest.mark.parametrize(
    "criteria",
    [
        TrialFilter(),
        TrialFilter(material="PMMA", flow_direction=FlowDirection.OPPOSED),
        TrialFilter(material="PMMA", flow_direction=FlowDirection.CONCURRENT),
    ],
    ids=["unfiltered", "pmma-opposed", "pmma-concurrent"],
)
def test_demo_question_is_refused_or_fully_grounded(
    settings: Settings, criteria: TrialFilter
) -> None:
    assistant = build_container(settings).assistant
    answer = assistant.execute(AssistantQuery(DEMO, criteria, "flame_spread_rate"))

    assert all(not t.is_synthetic for t in answer.trials)
    if answer.tier is EvidenceTier.INSUFFICIENT:
        assert answer.explanation is None and answer.refusal_reason
        return

    assert answer.explanation is not None
    usable_ids = {
        a.trial_id for a in answer.assessments if a.tier is not EvidenceTier.INSUFFICIENT
    }
    packet = EvidencePacket(
        DEMO,
        [t for t in answer.trials if t.id in usable_ids],
        answer.computed_facts,
        answer.documents,
        answer.limitations,
    )
    assert unsupported_numbers(answer.explanation.text, packet) == []
    assert set(answer.explanation.cited_sources) <= allowed_sources(packet)
    for fact in answer.computed_facts:
        assert "(measured" in fact or "(derived" in fact  # never extracted/synthetic


def test_out_of_scope_is_refused_on_curated_data(settings: Settings) -> None:
    assistant = build_container(settings).assistant
    answer = assistant.execute(
        AssistantQuery("Is PMMA safe for a lunar habitat?", TrialFilter(material="PMMA"))
    )
    assert answer.tier is EvidenceTier.INSUFFICIENT
    assert answer.refusal_reason and answer.refusal_reason.startswith("Out of scope")
