"""ExplanationGenerator backed by Claude (Anthropic API).

The model receives ONLY the audited EvidencePacket: trial facts computed by the domain and
retrieved document chunks (as citable documents). It writes the Interpretation section;
it never computes numbers. The use case renders "Observed evidence" and "Limitations"
itself and audits this output (unknown numbers -> deterministic fallback).

Citations are resolved from the API's structured citation objects by `document_index`,
i.e. to the exact chunk we sent. A citation whose index does not point at a document of
the packet is discarded, so a reference can never appear that was not retrieved. The quoted
passage (`cited_text`) is kept with the chunk id, so the UI can highlight it in the source.

The model is chosen per question from the offered list (`MODEL_CATALOG`); the configured
default applies when a question names none.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import anthropic
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaOutputConfigParam,
    BetaRequestDocumentBlockParam,
    BetaTextBlockParam,
    BetaUserMessageParam,
)

from prometeo.application.ports.outbound import (
    Citation,
    EvidencePacket,
    ExplainerModel,
    Explanation,
)
from prometeo.application.use_cases.ask_research_assistant import (
    DETERMINISTIC_MODEL,
    deterministic_interpretation,
)

Effort = Literal["low", "medium", "high", "xhigh", "max"]

DEFAULT_MODEL = "claude-sonnet-5-5"

# Models a question may choose, with the label and one-line trade-off shown in the picker.
MODEL_CATALOG: dict[str, tuple[str, str]] = {
    "claude-sonnet-5-5": ("Claude Sonnet 5.5", "Balanced speed and depth (default)"),
    "claude-opus-5-5": ("Claude Opus 5.5", "Most thorough reasoning, slower"),
    "claude-haiku-5-5": ("Claude Haiku 5.5", "Fastest, shortest interpretations"),
}

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def explainer_models(model_ids: Sequence[str]) -> tuple[ExplainerModel, ...]:
    """Picker entries for `model_ids`, in order; an id outside the catalog is shown as is."""
    out: list[ExplainerModel] = []
    for model_id in dict.fromkeys(model_ids):
        label, description = MODEL_CATALOG.get(model_id, (model_id, "Configured model"))
        out.append(ExplainerModel(model_id, label, description))
    return tuple(out)


def _has_server_side_fallback(model: str) -> bool:
    # Claude Haiku has no server-side refusal fallback: `fallbacks` must not be sent with it.
    return not model.startswith("claude-haiku")

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
- A document may describe another material, geometry, flow direction or investigation than \
the trials in the facts. When it does, say so where you use it and present it as background, \
not as an explanation of these trials. A number quoted from a document belongs to that \
document's conditions; never present it as a result of the listed trials.
- Describe uncontrolled conditions exactly as the limitations do: a condition listed as \
unknown is unknown, not different.
- When a limitation says trials are condition points on the same physical sample, say so \
when you describe a trend across them: they are one experimental sequence, not independent \
replicates.
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
        model: str = DEFAULT_MODEL,
        effort: Effort = "high",
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic()  # credentials from environment
        self._model = model
        self._effort = effort

    def explain(self, packet: EvidencePacket, model: str | None = None) -> Explanation:
        model_id = model or self._model
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
        messages = [BetaUserMessageParam(role="user", content=content)]
        try:
            if _has_server_side_fallback(model_id):
                # On a safety-classifier decline the API re-runs the request on a fallback
                # model inside the same call, routed by refusal category.
                response = self._client.beta.messages.create(
                    model=model_id,
                    max_tokens=16000,
                    system=SYSTEM_PROMPT,
                    output_config=output_config,
                    betas=[_FALLBACK_BETA],
                    fallbacks="default",
                    messages=messages,
                )
            else:
                response = self._client.beta.messages.create(
                    model=model_id,
                    max_tokens=16000,
                    system=SYSTEM_PROMPT,
                    output_config=output_config,
                    messages=messages,
                )
        except anthropic.AnthropicError as exc:
            # Missing credentials, network or API failure: degrade to the deterministic
            # interpretation instead of failing the request. The model field says why.
            return self._deterministic(packet, f"anthropic unavailable: {type(exc).__name__}")

        if response.stop_reason == "refusal":
            return self._deterministic(packet, f"{response.model} declined")

        parts: list[str] = []
        sources: list[str] = []
        quoted: list[Citation] = []
        for block in response.content:
            if block.type != "text":
                continue
            parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                ref = _resolve_citation(citation, packet)
                if ref is None:
                    continue
                if ref not in sources:
                    sources.append(ref)
                passage = _quoted_passage(citation, packet)
                if passage and passage not in quoted:
                    quoted.append(passage)
        return Explanation("".join(parts).strip(), tuple(sources), response.model, tuple(quoted))

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


def _quoted_passage(citation: object, packet: EvidencePacket) -> Citation | None:
    """The chunk and the text the model quoted from it. Call after `_resolve_citation`."""
    text = getattr(citation, "cited_text", None)
    if not isinstance(text, str) or not text.strip():
        return None
    index = getattr(citation, "document_index", 0)
    return Citation(packet.documents[index].id, text.strip())
