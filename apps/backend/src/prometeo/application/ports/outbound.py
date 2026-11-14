"""Outbound (driven) ports. Adapters in `prometeo.adapters.outbound` implement these.

Ports speak domain types only — never ORM rows, HTTP payloads or vendor SDK objects.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Provenance, Trial
from prometeo.domain.flamevision.model import Calibration, FlameFrontTrack


class TrialRepository(Protocol):
    def get(self, trial_id: str) -> Trial | None: ...
    def search(self, criteria: TrialFilter) -> list[Trial]: ...
    def list_all(self) -> list[Trial]: ...


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    id: str
    text: str
    provenance: Provenance
    score: float = 0.0


class DocumentRetriever(Protocol):
    """Hybrid (text + vector) retrieval over pre-indexed NASA documents."""

    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]: ...


@dataclass(frozen=True, slots=True)
class EvidencePacket:
    """Everything the explanation model may use. It must not add facts beyond this."""

    question: str
    trials: Sequence[Trial]
    computed_facts: Sequence[str]
    documents: Sequence[DocumentChunk]
    limitations: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Explanation:
    text: str
    cited_sources: tuple[str, ...]
    model: str


class ExplanationGenerator(Protocol):
    """Writes the narrative. Runs LAST, after retrieval, validation and computation."""

    def explain(self, packet: EvidencePacket) -> Explanation: ...


class FlameFrontDetector(Protocol):
    def track(
        self, trial_id: str, video_uri: str, calibration: Calibration
    ) -> FlameFrontTrack: ...
