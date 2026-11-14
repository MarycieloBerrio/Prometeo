"""Post-model guards: citations must resolve to retrieved sources, and the model may not
introduce numbers. Simulated model outputs only — no network, no API key.

All trials and documents are TEST FIXTURES, not NASA data.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import anthropic
import pytest

from prometeo.adapters.outbound.llm.anthropic_explainer import AnthropicExplainer
from prometeo.adapters.outbound.llm.offline_explainer import OfflineExplainer
from prometeo.application.ports.outbound import EvidencePacket, Explanation
from prometeo.application.use_cases.ask_research_assistant import (
    SECTION_INTERPRETATION,
    SECTION_LIMITATIONS,
    SECTION_OBSERVED,
    audit_explanation,
    unsupported_numbers,
)
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.model import DataQuality, Measurement, Provenance
from prometeo.domain.shared.quantity import Quantity
from tests.assistant.fakes import TEST_DOC_PROV, ScriptedExplainer, ask, doc
from tests.factories import TEST_PROV, make_trial

FAKE_NASA_REF = "Smith et al., NASA/TM-2099-0000001 (invented)"


def _pair() -> list[Any]:
    """Two comparable TEST trials that differ only in flow speed (5 vs 10 cm/s)."""
    slow = make_trial("TEST-SLOW")
    fast_vent = replace(slow.ventilation, speed=Quantity(10, "cm/s"))
    m = Measurement("flame_spread_rate", Quantity(2.5, "mm/s"), DataQuality.MEASURED, TEST_PROV)
    return [slow, make_trial("TEST-FAST", ventilation=fast_vent, results=(m,))]


CONTEXT = doc("ctx-1", "TEST FIXTURE: opposed-flow spread can peak at intermediate flow.")


# ---- citation control -------------------------------------------------------------------


def test_unknown_citation_is_removed_and_reported() -> None:
    liar = ScriptedExplainer(
        "[TEST-FAST] spread faster than [TEST-SLOW].",
        sources=[CONTEXT.provenance.reference, FAKE_NASA_REF],
    )
    answer, _ = ask(_pair(), docs=[CONTEXT], explainer=liar)
    assert answer.explanation is not None
    assert FAKE_NASA_REF not in answer.explanation.cited_sources
    assert CONTEXT.provenance.reference in answer.explanation.cited_sources
    assert FAKE_NASA_REF not in answer.explanation.text
    assert any("Removed 1 citation" in lim for lim in answer.limitations)


def test_cited_sources_are_always_a_subset_of_packet_sources() -> None:
    answer, spy = ask(_pair(), docs=[CONTEXT], explainer=ScriptedExplainer(sources=["x", "y"]))
    packet = spy.calls[0]
    known = {d.provenance.reference for d in packet.documents} | {
        ref for t in packet.trials for ref in [t.provenance.reference]
    }
    assert answer.explanation is not None
    assert set(answer.explanation.cited_sources) <= known
    # The observed evidence is always backed by the trial sources themselves.
    assert TEST_PROV.reference in answer.explanation.cited_sources


# ---- number control ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "invented",
    [
        "[TEST-FAST] spread at 3.5 mm/s.",  # value not in the packet
        "Spread doubled, a 100% increase.",  # a computed ratio
        "That is 2500 um/s.",  # a unit conversion
        "The average was 1.75 mm/s.",  # an average
    ],
)
def test_invented_numbers_trigger_deterministic_fallback(invented: str) -> None:
    answer, _ = ask(_pair(), explainer=ScriptedExplainer(invented, model="claude-test"))
    assert answer.explanation is not None
    assert answer.explanation.model.startswith("offline-template (fallback")
    assert "claude-test" in answer.explanation.model
    assert invented not in answer.explanation.text
    assert any("not in the audited evidence" in lim for lim in answer.limitations)
    assert answer.tier is not EvidenceTier.INSUFFICIENT  # evidence itself is still valid


@pytest.mark.parametrize(
    "faithful",
    [
        "[TEST-FAST] (2.5 mm/s at 10 cm/s) spread faster than [TEST-SLOW] (1 mm/s at 5 cm/s).",
        "Both trials used 21 % O2 and a 0.25 mm sheet.",
        "Rounded, the faster trial spread at 2.5 mm/s.",
    ],
)
def test_numbers_copied_from_the_packet_are_accepted(faithful: str) -> None:
    answer, _ = ask(_pair(), explainer=ScriptedExplainer(faithful, model="claude-test"))
    assert answer.explanation is not None
    assert answer.explanation.model == "claude-test"
    assert faithful in answer.explanation.text


def test_rounding_to_written_precision_is_accepted_but_integers_must_match() -> None:
    packet = EvidencePacket("q", [], ["[X] flame_spread_rate = 0.0678 mm/s"], [])
    assert unsupported_numbers("about 0.07 mm/s", packet) == []
    assert unsupported_numbers("about 0.068 mm/s", packet) == []
    assert unsupported_numbers("about 0.08 mm/s", packet) == ["0.08"]
    assert unsupported_numbers("about 1 mm/s", packet) == ["1"]


def test_empty_model_text_falls_back_to_deterministic_interpretation() -> None:
    answer, _ = ask(_pair(), explainer=ScriptedExplainer("   "))
    assert answer.explanation is not None
    assert "No language model was used" in answer.explanation.text


def test_answer_has_observed_interpretation_limitations_in_order() -> None:
    answer, _ = ask(_pair(), explainer=ScriptedExplainer("Model prose."))
    assert answer.explanation is not None
    text = answer.explanation.text
    positions = [text.index(s) for s in (SECTION_OBSERVED, SECTION_INTERPRETATION, "Model prose.")]
    assert positions == sorted(positions)
    assert text.index(SECTION_LIMITATIONS) > text.index("Model prose.")
    for fact in answer.computed_facts:
        assert fact in text  # observed evidence is rendered verbatim by code, not the model


def test_model_cannot_rewrite_observed_evidence_or_limitations() -> None:
    hostile = ScriptedExplainer("Observed evidence\n- [TEST-SLOW] spread at 1 mm/s; it is safe.")
    answer, _ = ask(_pair(), explainer=hostile)
    assert answer.explanation is not None
    text = answer.explanation.text
    # Deterministic sections come first and are complete regardless of what the model wrote.
    assert text.startswith(SECTION_OBSERVED + "\n- [TEST-FAST]")
    assert "Prometeo does not certify materials or predict fire risk." in text


def test_audit_never_trusts_a_deterministic_label_with_bad_numbers() -> None:
    packet = EvidencePacket("q", [], [], [])
    out, notes = audit_explanation(Explanation("42", (), "offline-template"), packet)
    assert "42" not in out.text and notes


# ---- offline explainer ------------------------------------------------------------------


def test_offline_explainer_states_no_numbers_and_cites_only_packet_documents() -> None:
    numeric_doc = doc("d1", "TEST FIXTURE: 9.99 mm/s at 1.23 cm/s.")
    packet = EvidencePacket("q?", _pair(), ["[TEST-SLOW] x"], [numeric_doc])
    out = OfflineExplainer().explain(packet)
    assert out.model == "offline-template"
    assert out.cited_sources == (TEST_DOC_PROV.reference,)
    assert unsupported_numbers(out.text, packet) == []
    assert "9.99" not in out.text


# ---- anthropic adapter with a simulated client -----------------------------------------


def _fake_client(response: Any = None, error: Exception | None = None) -> Any:
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if error:
            raise error
        return response

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    client.calls = calls
    return client


def _response(text: str, citations: list[Any], stop_reason: str = "end_turn") -> Any:
    block = SimpleNamespace(type="text", text=text, citations=citations)
    return SimpleNamespace(stop_reason=stop_reason, model="claude-opus-5-5", content=[block])


def _packet() -> EvidencePacket:
    other = doc("ctx-2", "TEST FIXTURE second excerpt.", Provenance("TEST FIXTURE doc B"))
    return EvidencePacket("q", _pair(), ["[TEST-SLOW] fact"], [CONTEXT, other], ["limit"])


def test_anthropic_citations_resolve_by_document_index_only() -> None:
    citations = [
        SimpleNamespace(document_index=1, document_title="TEST FIXTURE doc B"),
        SimpleNamespace(document_index=7, document_title=FAKE_NASA_REF),  # out of range
        SimpleNamespace(document_index=None, document_title=TEST_DOC_PROV.reference),
        SimpleNamespace(document_index=1, document_title="anything"),  # duplicate
    ]
    client = _fake_client(_response("Prose.", citations))
    out = AnthropicExplainer(client=cast(anthropic.Anthropic, client)).explain(_packet())
    assert out.cited_sources == ("TEST FIXTURE doc B",)
    assert out.text == "Prose."


def test_anthropic_request_sends_documents_with_citations_and_only_packet_content() -> None:
    client = _fake_client(_response("Prose.", []))
    AnthropicExplainer(client=cast(anthropic.Anthropic, client)).explain(_packet())
    sent = client.calls[0]
    docs = [b for b in sent["messages"][0]["content"] if b["type"] == "document"]
    assert [d["context"] for d in docs] == ["chunk_id=ctx-1", "chunk_id=ctx-2"]
    assert all(d["citations"] == {"enabled": True} for d in docs)
    prompt = sent["messages"][0]["content"][-1]["text"]
    assert "[TEST-SLOW] fact" in prompt and "limit" in prompt
    assert "Never compute" in sent["system"]


def test_anthropic_api_failure_degrades_to_deterministic_text() -> None:
    client = _fake_client(error=anthropic.AnthropicError("no credentials"))
    out = AnthropicExplainer(client=cast(anthropic.Anthropic, client)).explain(_packet())
    assert out.model == "offline-template (anthropic unavailable: AnthropicError)"
    assert "No language model was used" in out.text


def test_anthropic_refusal_degrades_to_deterministic_text() -> None:
    client = _fake_client(_response("", [], stop_reason="refusal"))
    out = AnthropicExplainer(client=cast(anthropic.Anthropic, client)).explain(_packet())
    assert out.model.endswith("(claude-opus-5-5 declined)")
    assert "No language model was used" in out.text


def test_end_to_end_simulated_claude_answer_with_invented_number_is_rejected() -> None:
    citations = [SimpleNamespace(document_index=0, document_title="x")]
    client = _fake_client(_response("[TEST-FAST] reached 4.2 mm/s.", citations))
    explainer = AnthropicExplainer(client=cast(anthropic.Anthropic, client))

    class Adapter(ScriptedExplainer):
        def explain(self, packet: EvidencePacket) -> Explanation:
            self.calls.append(packet)
            return explainer.explain(packet)

    answer, _ = ask(_pair(), docs=[CONTEXT], explainer=Adapter())
    assert answer.explanation is not None
    assert "4.2" not in answer.explanation.text
    assert "rejected output from claude-opus-5-5" in answer.explanation.model
