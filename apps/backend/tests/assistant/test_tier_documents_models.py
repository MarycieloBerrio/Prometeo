"""Evidence tier of a comparable set, document order by investigation, quoted passages and
the per-question model choice.

All trials and documents are TEST FIXTURES, not NASA data.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import anthropic
import pytest

from prometeo.adapters.inbound.http.schemas import ask_out
from prometeo.adapters.outbound.llm.anthropic_explainer import (
    DEFAULT_MODEL,
    AnthropicExplainer,
    explainer_models,
)
from prometeo.application.ports.outbound import Citation, DocumentChunk, EvidencePacket
from prometeo.application.use_cases.ask_research_assistant import (
    document_relation,
    prioritize_documents,
)
from prometeo.bootstrap.settings import Settings
from prometeo.domain.evidence.ranking import EvidenceTier
from prometeo.domain.experiments.model import DataQuality, Measurement, Trial
from prometeo.domain.shared.quantity import Quantity
from tests.assistant.fakes import ScriptedExplainer, ask, doc
from tests.factories import TEST_PROV, make_trial


def _pair(**overrides: Any) -> list[Trial]:
    """Two comparable TEST trials that differ only in flow speed (5 vs 10 cm/s)."""
    slow = make_trial("TEST-SLOW", **overrides)
    fast_vent = replace(slow.ventilation, speed=Quantity(10, "cm/s"))
    m = Measurement("flame_spread_rate", Quantity(2.5, "mm/s"), DataQuality.MEASURED, TEST_PROV)
    return [slow, make_trial("TEST-FAST", ventilation=fast_vent, results=(m,), **overrides)]


def _tier_note(limitations: tuple[str, ...]) -> str | None:
    return next((lim for lim in limitations if lim.startswith("Evidence tier is partial")), None)


# ---- tier: direct means a controlled comparison ---------------------------------------------


def test_one_varied_condition_with_everything_else_recorded_is_direct() -> None:
    answer, _ = ask(_pair())
    assert answer.tier is EvidenceTier.DIRECT
    assert _tier_note(answer.limitations) is None


def test_identical_conditions_on_independent_samples_are_direct() -> None:
    answer, _ = ask([make_trial("TEST-A"), make_trial("TEST-B")])
    assert answer.tier is EvidenceTier.DIRECT


def test_an_unknown_condition_caps_the_tier_at_partial() -> None:
    answer, _ = ask(_pair(pressure=None))
    assert answer.tier is EvidenceTier.PARTIAL
    note = _tier_note(answer.limitations)
    assert note is not None and "pressure is unknown for at least one trial" in note


def test_two_varied_conditions_cap_the_tier_at_partial() -> None:
    slow, fast = _pair()
    answer, _ = ask([slow, replace(fast, oxygen=Quantity(18, "%"))])
    assert answer.tier is EvidenceTier.PARTIAL
    note = _tier_note(answer.limitations)
    assert note is not None and "more than one condition differs (flow_speed, oxygen)" in note


def test_a_series_on_one_physical_sample_caps_the_tier_at_partial() -> None:
    answer, _ = ask(_pair(sample_id="TEST-S1"))
    assert answer.tier is EvidenceTier.PARTIAL
    note = _tier_note(answer.limitations)
    assert note is not None and "condition points on one physical sample" in note


def test_the_cap_never_turns_a_refusal_into_an_answer() -> None:
    answer, _ = ask([make_trial("TEST-ONLY", pressure=None)])
    assert answer.tier is EvidenceTier.INSUFFICIENT and answer.explanation is None


# ---- documents: the trials' own investigation first -----------------------------------------


def _doc(chunk_id: str, investigation: str | None, related: tuple[str, ...] = ()) -> DocumentChunk:
    text = "TEST FIXTURE " + " ".join(f"{chunk_id}word{i}" for i in range(8))
    return replace(doc(chunk_id, text), investigation=investigation, related_investigations=related)


def test_documents_are_ordered_same_then_related_then_other_keeping_rank_inside() -> None:
    ranked = [
        _doc("gas-1", "TEST-GAS"),
        _doc("own-1", "BASS-II"),
        _doc("sibling-1", "TEST-SIBLING", ("BASS-II",)),
        _doc("unknown-1", None),
        _doc("own-2", "BASS-II"),
        _doc("gas-2", "TEST-GAS"),
    ]
    ordered = prioritize_documents(ranked, frozenset({"BASS-II"}))
    assert [d.id for d in ordered] == ["own-1", "own-2", "sibling-1", "gas-1", "unknown-1", "gas-2"]


def test_without_usable_trials_the_retriever_order_is_kept() -> None:
    ranked = [_doc("gas-1", "TEST-GAS"), _doc("own-1", "BASS-II")]
    assert prioritize_documents(ranked, frozenset()) == ranked
    assert document_relation(ranked[1], frozenset()) == "other"


def test_answer_lists_the_trials_investigation_first_and_reports_the_relation() -> None:
    docs = [
        _doc("gas-1", "TEST-GAS"),
        _doc("sibling-1", "TEST-SIBLING", ("BASS-II",)),
        _doc("own-1", "BASS-II"),  # make_trial records investigation BASS-II
    ]
    answer, spy = ask(_pair(), docs=docs)
    assert [d.id for d in answer.documents] == ["own-1", "sibling-1", "gas-1"]
    assert [d.id for d in spy.calls[0].documents] == ["own-1", "sibling-1", "gas-1"]
    out = ask_out(answer)
    assert [(d.id, d.investigation, d.relation) for d in out.documents] == [
        ("own-1", "BASS-II", "same"),
        ("sibling-1", "TEST-SIBLING", "related"),
        ("gas-1", "TEST-GAS", "other"),
    ]


# ---- quoted passages are verbatim slices of the retrieved chunk ----------------------------

PASSAGE = "TEST FIXTURE: the flame is initially sooty. As flow is reduced, sooting disappears."


def test_only_verbatim_quotations_of_a_retrieved_chunk_are_kept() -> None:
    explainer = ScriptedExplainer("Prose.", sources=[])
    explainer.citations = (
        Citation("ctx", "As flow is reduced,   sooting\ndisappears."),  # whitespace differs
        Citation("ctx", "As flow is reduced, sooting disappears."),  # duplicate once squashed
        Citation("ctx", "Sooting increases with flow."),  # not in the chunk
        Citation("missing", "the flame is initially sooty"),  # chunk was never retrieved
        Citation("ctx", "   "),
    )
    answer, _ = ask(_pair(), docs=[doc("ctx", PASSAGE)], explainer=explainer)
    assert answer.citations == (Citation("ctx", "As flow is reduced, sooting disappears."),)
    out = ask_out(answer)
    assert out.documents[0].cited_passages == ["As flow is reduced, sooting disappears."]
    assert out.documents[0].cited_passages[0] in " ".join(out.documents[0].excerpt.split())


def test_a_rejected_interpretation_carries_no_quotations() -> None:
    explainer = ScriptedExplainer("[TEST-FAST] reached 9.99 mm/s.")  # invented number
    explainer.citations = (Citation("ctx", "the flame is initially sooty"),)
    answer, _ = ask(_pair(), docs=[doc("ctx", PASSAGE)], explainer=explainer)
    assert answer.citations == ()
    assert ask_out(answer).documents[0].cited_passages == []


# ---- model choice -----------------------------------------------------------------------


def test_the_question_s_model_reaches_the_explainer_and_none_means_default() -> None:
    _, spy = ask(_pair(), model="claude-opus-5-5")
    assert spy.requested_models == ["claude-opus-5-5"]
    _, spy = ask(_pair())
    assert spy.requested_models == [None]


def test_default_model_is_sonnet_and_is_always_offered_first() -> None:
    assert DEFAULT_MODEL == "claude-sonnet-5-5"
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.anthropic_model == "claude-sonnet-5-5"
    assert settings.anthropic_model_choices()[0] == "claude-sonnet-5-5"
    custom = Settings(
        _env_file=None,  # type: ignore[call-arg]
        anthropic_model="claude-haiku-5-5",
        anthropic_models="claude-opus-5-5, claude-haiku-5-5,,claude-opus-5-5",
    )
    assert custom.anthropic_model_choices() == ["claude-haiku-5-5", "claude-opus-5-5"]


def test_picker_entries_have_labels_and_keep_unknown_ids() -> None:
    models = explainer_models(["claude-sonnet-5-5", "test-model", "claude-sonnet-5-5"])
    assert [m.id for m in models] == ["claude-sonnet-5-5", "test-model"]
    assert models[0].label == "Claude Sonnet 5.5" and models[1].label == "test-model"


def _client(response: Any) -> Any:
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return response

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    client.calls = calls
    return client


def _response(model: str, citations: list[Any]) -> Any:
    block = SimpleNamespace(type="text", text="Prose.", citations=citations)
    return SimpleNamespace(stop_reason="end_turn", model=model, content=[block])


def _packet() -> EvidencePacket:
    return EvidencePacket("q", _pair(), ["[TEST-SLOW] fact"], [doc("ctx", PASSAGE)], ["limit"])


@pytest.mark.parametrize(
    ("requested", "sent", "fallback"),
    [
        (None, "claude-sonnet-5-5", True),
        ("claude-opus-5-5", "claude-opus-5-5", True),
        ("claude-haiku-5-5", "claude-haiku-5-5", False),  # Haiku has no server-side fallback
    ],
)
def test_anthropic_request_uses_the_chosen_model_and_fallbacks_only_where_supported(
    requested: str | None, sent: str, fallback: bool
) -> None:
    client = _client(_response(sent, []))
    explainer = AnthropicExplainer(client=cast(anthropic.Anthropic, client))
    out = explainer.explain(_packet(), requested)
    call = client.calls[0]
    assert call["model"] == sent and out.model == sent
    assert ("fallbacks" in call) is fallback and ("betas" in call) is fallback
    assert call["output_config"] == {"effort": "high"}


def test_anthropic_quotations_carry_the_chunk_id_of_the_cited_document() -> None:
    citations = [
        SimpleNamespace(document_index=0, cited_text=" the flame is initially sooty "),
        SimpleNamespace(document_index=0, cited_text="the flame is initially sooty"),
        SimpleNamespace(document_index=5, cited_text="out of range"),
        SimpleNamespace(document_index=0, cited_text=None),
    ]
    client = _client(_response("claude-sonnet-5-5", citations))
    out = AnthropicExplainer(client=cast(anthropic.Anthropic, client)).explain(_packet())
    assert out.citations == (Citation("ctx", "the flame is initially sooty"),)
