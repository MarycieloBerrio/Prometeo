"""KeywordRetriever: offline, deterministic, defensive about the corpus, and faithful to
provenance. The corpus written here is a TEST FIXTURE in Yulian's curated chunk format
(data/README.md); its text and references are invented, not NASA content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from prometeo.adapters.outbound.retrieval.keyword_retriever import KeywordRetriever


def _write(tmp_path: Path, entries: list[Any]) -> Path:
    path = tmp_path / "document_chunks.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _chunk(chunk_id: str, text: str, **prov: Any) -> dict[str, Any]:
    provenance = {"reference": f"TEST ref {chunk_id}", **prov}
    return {"id": chunk_id, "text": text, "provenance": provenance}


CORPUS = [
    _chunk(
        "opposed-peak",
        "TEST FIXTURE: in opposed flow the flame spread rate first increased then decreased "
        "as flow speed increased.",
        url="https://example.invalid/a",
        page="Fig. 6",
        doi="10.0000/test-a",
    ),
    _chunk("o2-limit", "TEST FIXTURE: spread was observed at reduced O₂ concentration."),
    _chunk("heat-release", "TEST FIXTURE: heat release estimated from oxygen consumption."),
    _chunk("unrelated", "TEST FIXTURE: crew procedures for stowage."),
]


def test_missing_file_or_none_path_gives_an_empty_offline_retriever(tmp_path: Path) -> None:
    assert KeywordRetriever(None).retrieve("flame spread") == []
    assert KeywordRetriever(tmp_path / "nope.json").retrieve("flame spread") == []


def test_ranks_the_chunk_that_answers_the_question_first(tmp_path: Path) -> None:
    r = KeywordRetriever(_write(tmp_path, CORPUS))
    hits = r.retrieve("How does flame spread rate change with opposed flow speed?")
    assert hits[0].id == "opposed-peak"
    assert "unrelated" not in [h.id for h in hits]
    assert all(0 < h.score <= 1 for h in hits)


def test_vocabulary_variants_match(tmp_path: Path) -> None:
    r = KeywordRetriever(_write(tmp_path, CORPUS))
    assert r.retrieve("ventilation velocity")[0].id == "opposed-peak"  # -> flow speed
    assert r.retrieve("oxygen concentration")[0].id == "o2-limit"  # O₂ folded to o2
    assert r.retrieve("O2")[0].id in {"o2-limit", "heat-release"}


def test_provenance_is_preserved_verbatim_and_never_invented(tmp_path: Path) -> None:
    r = KeywordRetriever(_write(tmp_path, CORPUS))
    by_id = {h.id: h for h in r.retrieve("flame spread flow oxygen O2", limit=10)}
    full = by_id["opposed-peak"].provenance
    assert (full.reference, full.url, full.page, full.doi) == (
        "TEST ref opposed-peak", "https://example.invalid/a", "Fig. 6", "10.0000/test-a",
    )
    bare = by_id["o2-limit"].provenance
    assert (bare.url, bare.page, bare.doi, bare.source_file) == (None, None, None, None)


def test_blank_metadata_stays_unknown(tmp_path: Path) -> None:
    entries = [_chunk("c", "TEST FIXTURE flame spread", doi="  ", page="", url=None)]
    hit = KeywordRetriever(_write(tmp_path, entries)).retrieve("flame")[0]
    assert (hit.provenance.doi, hit.provenance.page, hit.provenance.url) == (None, None, None)


def test_incomplete_and_duplicate_entries_are_rejected_not_served(tmp_path: Path) -> None:
    entries = [
        *CORPUS,
        {"id": "", "text": "flame", "provenance": {"reference": "r"}},
        {"id": "no-text", "text": "   ", "provenance": {"reference": "r"}},
        {"id": "no-prov", "text": "flame spread"},
        {"id": "no-ref", "text": "flame spread", "provenance": {"url": "https://x.invalid"}},
        "not an object",
        _chunk("opposed-peak", "a different text under a repeated id"),
        {**CORPUS[1], "id": "o2-limit-copy"},  # same text and reference, new id
        {"id": "stop", "text": "the of and", "provenance": {"reference": "r"}},
    ]
    r = KeywordRetriever(_write(tmp_path, entries))
    assert r.size == len(CORPUS)
    assert len(r.rejected) == 8
    reasons = " | ".join(r.rejected)
    for expected in ("missing id", "no-text: empty text", "missing provenance reference",
                     "duplicate id", "duplicate text", "no indexable words"):
        assert expected in reasons
    served = {h.id for h in r.retrieve("flame spread repeated different text O2", limit=50)}
    assert served <= {c["id"] for c in CORPUS}


def test_non_list_corpus_is_a_loud_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"id": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON list"):
        KeywordRetriever(path)


def test_ties_break_deterministically_by_id(tmp_path: Path) -> None:
    twins = [_chunk(i, "TEST FIXTURE flame spread") for i in ("b-twin", "a-twin", "c-twin")]
    # Different references so the duplicate-content guard keeps all three.
    r = KeywordRetriever(_write(tmp_path, twins))
    first = [h.id for h in r.retrieve("flame spread")]
    assert first == ["a-twin", "b-twin", "c-twin"]
    assert [h.id for h in r.retrieve("flame spread")] == first


@pytest.mark.parametrize("query", ["", "   ", "the of and", "?!"])
def test_empty_or_stopword_queries_return_nothing(tmp_path: Path, query: str) -> None:
    assert KeywordRetriever(_write(tmp_path, CORPUS)).retrieve(query) == []


def test_limit_is_respected(tmp_path: Path) -> None:
    r = KeywordRetriever(_write(tmp_path, CORPUS))
    assert len(r.retrieve("TEST FIXTURE", limit=2)) == 2
    assert r.retrieve("TEST FIXTURE", limit=0) == []
