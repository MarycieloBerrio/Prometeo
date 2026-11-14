"""Deterministic, template-based ExplanationGenerator.

Used in tests, CI and local development without an API key. It writes the Interpretation
section only (the use case renders "Observed evidence" and "Limitations" around it) and
never states a number: the deterministic interpretation is the baseline any model output
must not contradict, and the fallback the use case switches to when a model output fails
its audit.
"""

from __future__ import annotations

from prometeo.application.ports.outbound import EvidencePacket, Explanation
from prometeo.application.use_cases.ask_research_assistant import (
    DETERMINISTIC_MODEL,
    deterministic_interpretation,
)


class OfflineExplainer:
    def explain(self, packet: EvidencePacket) -> Explanation:
        # Only documents that the text actually names are cited, and only by their recorded
        # reference — no DOI, page or URL is ever synthesized here.
        sources = tuple(dict.fromkeys(d.provenance.reference for d in packet.documents))
        return Explanation(deterministic_interpretation(packet), sources, DETERMINISTIC_MODEL)
