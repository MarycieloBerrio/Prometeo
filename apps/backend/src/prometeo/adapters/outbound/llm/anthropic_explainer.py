"""ExplanationGenerator backed by Claude (Anthropic API).

The model receives ONLY the audited EvidencePacket: trial facts computed by the domain and
retrieved document chunks (as citable documents). It writes the Interpretation section;
it never computes numbers. The use case renders "Observed evidence" and "Limitations"
itself and audits this output (unknown numbers -> deterministic fallback).

Citations are resolved from the API's structured citation objects by `document_index`,
i.e. to the exact chunk we sent. A citation whose index does not point at a document of
the packet is discarded, so a reference can never appear that was not retrieved.
"""

from __future__ import annotations

from typing import Literal

import anthropic
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaOutputConfigParam,
    BetaRequestDocumentBlockParam,
    BetaTextBlockParam,
    BetaUserMessageParam,
)

from prometeo.application.ports.outbound import EvidencePacket, Explanation
from prometeo.application.use_cases.ask_research_assistant import (
    DETERMINISTIC_MODEL,
    deterministic_interpretation,
)

Effort = Literal["low", "medium", "high", "xhigh", "max"]

SYSTEM_PROMPT = """\
You are the interpretation layer of Prometeo, a scientific evidence engine for microgravity \
combustion research (NASA BASS-II, FLEX, SAFFIRE).

Deterministic code has already selected the trials, validated their comparability, and will \
show the user an "Observed evidence" list (the facts you receive) and a "Limitations" list \
(the limitations you receive). You write ONLY the interpretation that sits between them: \
plain prose, no headings, no bullet lists, at most three short paragraphs.

Rules:
- Use only the facts and documents provided. Never compute, convert, average, or estimate a \
number. If you mention a value, copy it exactly as written in a fact, with its unit.
- Reference trials by their [id]. Cite a document only when you rely on its text.
- Keep three things distinct: what was observed (facts), the mechanism the documents propose \
for it, and what remains unsupported by this evidence.
- Treat each "Comparable set" as separate; never compare trials across sets. Never merge \
BASS-II, FLEX and SAFFIRE results as if they were one dataset.
- Never extrapolate to untested oxygen levels, flows, materials, gravity levels or scales. \
Never state or imply that a material is safe, certified, or has a probability of burning.
- If the facts do not answer the question, say so plainly instead of filling the gap.
"""


class AnthropicExplainer:
    def __init__(
        self,
        model: str = "claude-opus-5-5",
        effort: Effort = "high",
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic()  # credentials from environment
        self._model = model
        self._effort = effort

    def explain(self, packet: EvidencePacket) -> Explanation:
        content: list[BetaContentBlockParam] = [
            BetaRequestDocumentBlockParam(
                type="document",
                source={"type": "text", "media_type": "text/plain", "data": chunk.text},
                title=chunk.provenance.reference,
                context=f"chunk_id={chunk.id}",
                citations={"enabled": True},
            )
            for chunk in packet.documents
        ]
        facts = "\n".join(f"- {f}" for f in packet.computed_facts) or "- (none)"
        limits = "\n".join(f"- {lim}" for lim in packet.limitations) or "- (none)"
        prompt = (
            f"Question: {packet.question}\n\n"
            f"Observed evidence (validated facts):\n{facts}\n\n"
            f"Known limitations:\n{limits}\n\n"
            "Write the interpretation now."
        )
        content.append(BetaTextBlockParam(type="text", text=prompt))

        output_config: BetaOutputConfigParam = {"effort": self._effort}
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                output_config=output_config,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[BetaUserMessageParam(role="user", content=content)],
            )
        except anthropic.AnthropicError as exc:
            # Missing credentials, network or API failure: degrade to the deterministic
            # interpretation instead of failing the request. The model field says why.
            return self._deterministic(packet, f"anthropic unavailable: {type(exc).__name__}")

        if response.stop_reason == "refusal":
            return self._deterministic(packet, f"{response.model} declined")

        parts: list[str] = []
        sources: list[str] = []
        for block in response.content:
            if block.type != "text":
                continue
            parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                ref = _resolve_citation(citation, packet)
                if ref and ref not in sources:
                    sources.append(ref)
        return Explanation("".join(parts).strip(), tuple(sources), response.model)

    @staticmethod
    def _deterministic(packet: EvidencePacket, why: str) -> Explanation:
        refs = tuple(dict.fromkeys(d.provenance.reference for d in packet.documents))
        return Explanation(
            deterministic_interpretation(packet), refs, f"{DETERMINISTIC_MODEL} ({why})"
        )


def _resolve_citation(citation: object, packet: EvidencePacket) -> str | None:
    """Map an API citation to the provenance reference of the chunk it points at."""
    index = getattr(citation, "document_index", None)
    if not isinstance(index, int) or isinstance(index, bool):
        return None
    if not 0 <= index < len(packet.documents):
        return None
    return packet.documents[index].provenance.reference
