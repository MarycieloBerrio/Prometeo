"""ExplanationGenerator backed by Claude (Anthropic API).

The model receives ONLY the audited EvidencePacket: trial facts computed by the domain and
retrieved document chunks (as citable documents). It writes prose; it never computes numbers.
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

Effort = Literal["low", "medium", "high", "xhigh", "max"]

SYSTEM_PROMPT = """\
You are the explanation layer of Prometeo, a scientific evidence engine for microgravity \
combustion research (NASA BASS-II, FLEX, SAFFIRE).

You receive a question, a list of experimental facts already computed and validated by \
deterministic code, retrieved document excerpts, and known limitations.

Write a concise technical interpretation for engineers:
- Use only the facts and documents provided. Do not introduce numbers that are not in them.
- Reference trials by their [id] and cite documents when you rely on them.
- Separate observation, interpretation and what remains unsupported.
- Never extrapolate to untested oxygen levels, flows, materials, gravity levels or scales.
- If facts conflict or trials differ in conditions, explain why rather than averaging.
- End with the limitations that apply to this answer.
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
            f"Validated experimental facts:\n{facts}\n\n"
            f"Known limitations:\n{limits}"
        )
        content.append(BetaTextBlockParam(type="text", text=prompt))

        output_config: BetaOutputConfigParam = {"effort": self._effort}
        response = self._client.beta.messages.create(
            model=self._model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[BetaUserMessageParam(role="user", content=content)],
        )

        if response.stop_reason == "refusal":
            return Explanation(
                text="The explanation model declined to answer this request.",
                cited_sources=(),
                model=response.model,
            )

        parts: list[str] = []
        sources: list[str] = []
        for block in response.content:
            if block.type != "text":
                continue
            parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                title = getattr(citation, "document_title", None)
                if title and title not in sources:
                    sources.append(title)
        return Explanation("".join(parts), tuple(sources), response.model)
