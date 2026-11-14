"""Deterministic, template-based ExplanationGenerator.

Used in tests, CI and local development without an API key. It restates the audited
packet verbatim — useful as a baseline the LLM output must never contradict.
"""

from __future__ import annotations

from prometeo.application.ports.outbound import EvidencePacket, Explanation


class OfflineExplainer:
    def explain(self, packet: EvidencePacket) -> Explanation:
        lines = [f"Question: {packet.question}", "", "Recorded evidence:"]
        lines += [f"- {f}" for f in packet.computed_facts] or ["- (none)"]
        if packet.documents:
            lines += ["", "Related documents:"]
            lines += [f"- {d.provenance.reference}" for d in packet.documents]
        lines += ["", "Limitations:"] + [f"- {lim}" for lim in packet.limitations]
        sources = tuple(dict.fromkeys(d.provenance.reference for d in packet.documents))
        return Explanation("\n".join(lines), sources, model="offline-template")
