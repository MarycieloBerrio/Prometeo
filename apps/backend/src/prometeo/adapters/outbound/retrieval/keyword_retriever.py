"""Offline keyword retriever over pre-chunked documents (JSON). Baseline stand-in for
pgvector hybrid search; same `DocumentRetriever` port, so swapping is a wiring change.

Chunk file format: [{"id": str, "text": str, "provenance": {"reference": str, ...}}]
An entry may also name its "investigation" (e.g. "BASS-II"); it is never guessed from the text.

What this does — and does not — mean:
* Ranking is lexical (IDF-weighted term overlap plus a small bonus for adjacent query terms
  that appear adjacently in the chunk). A high score says the words match, NOT that the
  experiment behind the text is relevant, comparable or of good quality. Scientific
  admissibility is decided by EvidenceRank and the Physics Validator, never here.
* Provenance is copied verbatim from the file. A missing DOI, page or URL stays `None`;
  nothing is synthesized.
* Loading is defensive: entries without an id, text or provenance reference are skipped
  (and listed in `rejected`); repeated ids and repeated (text, reference) pairs keep the
  first occurrence, so a duplicated corpus cannot crowd out other sources.
* Results are deterministic: ties break on matched-term count, then chunk id.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass, replace
from itertools import pairwise
from pathlib import Path
from typing import Any

from prometeo.application.ports.outbound import DocumentChunk
from prometeo.domain.experiments.model import Provenance

_TOKEN = re.compile(r"[a-z0-9]+")

# Function words carry no topical signal; kept short and domain-neutral on purpose.
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "could",
        "did", "do", "does", "for", "from", "has", "have", "how", "in", "into", "is", "it",
        "its", "of", "on", "or", "so", "than", "that", "the", "their", "them", "then",
        "there", "these", "they", "this", "those", "to", "was", "were", "what", "when",
        "where", "which", "while", "who", "why", "will", "with", "would", "about",
    }
)

_PHRASE_WEIGHT = 0.15  # share of the score reserved for adjacent query-term pairs

# Lexical spelling variants mapped to one index term, applied to queries AND chunks. This is
# vocabulary normalization for recall ("ventilation speed" finds "opposed flow"), not a
# physical equivalence: flow direction, regime and comparability are judged elsewhere.
_CANONICAL = {
    "ventilation": "flow",
    "airflow": "flow",
    "oxygen": "o2",
    "velocity": "speed",
}


def _fold(text: str) -> str:
    # NFKD maps "O₂" -> "O2" and strips accents ("Damköhler" -> "Damkohler").
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _stem(token: str) -> str:
    # Minimal plural folding only ("flames" -> "flame", "rods" -> "rod"); no aggressive
    # stemming that could merge distinct scientific terms.
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _token_list(text: str) -> list[str]:
    out = []
    for raw in _TOKEN.findall(_fold(text)):
        if raw in _STOPWORDS:
            continue
        # Keep short tokens that carry digits ("o2", "n2", "1g"); drop other 1-2 letter words.
        if len(raw) < 3 and not any(ch.isdigit() for ch in raw):
            continue
        token = _stem(raw)
        out.append(_CANONICAL.get(token, token))
    return out


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(pairwise(tokens))


@dataclass(frozen=True, slots=True)
class _Indexed:
    chunk: DocumentChunk
    terms: frozenset[str]
    bigrams: frozenset[tuple[str, str]]


def _optional(p: dict[str, Any], key: str) -> str | None:
    value = p.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class KeywordRetriever:
    def __init__(self, path: Path | None) -> None:
        self._index: list[_Indexed] = []
        self._df: dict[str, int] = {}
        self.rejected: tuple[str, ...] = ()
        if path and path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError(f"{path}: expected a JSON list of document chunks")
            self._load(raw)

    def _load(self, entries: list[Any]) -> None:
        rejected: list[str] = []
        seen_ids: set[str] = set()
        seen_content: set[tuple[str, str]] = set()
        for n, entry in enumerate(entries):
            label = f"entry #{n}"
            if not isinstance(entry, dict):
                rejected.append(f"{label}: not an object")
                continue
            chunk_id = str(entry.get("id") or "").strip()
            text = str(entry.get("text") or "").strip()
            prov = entry.get("provenance")
            reference = _optional(prov, "reference") if isinstance(prov, dict) else None
            if not chunk_id:
                rejected.append(f"{label}: missing id")
                continue
            if not text:
                rejected.append(f"{chunk_id}: empty text")
                continue
            if not isinstance(prov, dict) or reference is None:
                rejected.append(f"{chunk_id}: missing provenance reference")
                continue
            if chunk_id in seen_ids:
                rejected.append(f"{chunk_id}: duplicate id")
                continue
            content_key = (" ".join(_fold(text).split()), reference)
            if content_key in seen_content:
                rejected.append(f"{chunk_id}: duplicate text for the same reference")
                continue
            seen_ids.add(chunk_id)
            seen_content.add(content_key)
            provenance = Provenance(
                reference=reference,
                source_file=_optional(prov, "source_file"),
                doi=_optional(prov, "doi"),
                url=_optional(prov, "url"),
                page=_optional(prov, "page"),
                version=_optional(prov, "version"),
            )
            tokens = _token_list(text)
            if not tokens:
                rejected.append(f"{chunk_id}: no indexable words")
                continue
            terms = frozenset(tokens)
            investigation = str(entry.get("investigation") or "").strip() or None
            self._index.append(
                _Indexed(
                    DocumentChunk(chunk_id, text, provenance, investigation=investigation),
                    terms,
                    frozenset(_bigrams(tokens)),
                )
            )
            for term in terms:
                self._df[term] = self._df.get(term, 0) + 1
        self.rejected = tuple(rejected)

    @property
    def size(self) -> int:
        """Number of indexed chunks (after rejecting incomplete or duplicate entries)."""
        return len(self._index)

    def _idf(self, term: str) -> float:
        n = len(self._index)
        df = self._df.get(term, 0)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]:
        if limit <= 0 or not self._index:
            return []
        q_tokens = _token_list(query)
        q_terms = set(q_tokens)
        if not q_terms:
            return []
        q_bigrams = _bigrams(q_tokens)
        total_idf = sum(self._idf(t) for t in q_terms)

        scored: list[tuple[float, int, str, DocumentChunk]] = []
        for item in self._index:
            matched = q_terms & item.terms
            if not matched:
                continue
            coverage = sum(self._idf(t) for t in matched) / total_idf
            phrase = len(q_bigrams & item.bigrams) / len(q_bigrams) if q_bigrams else 0.0
            score = round((1 - _PHRASE_WEIGHT) * coverage + _PHRASE_WEIGHT * phrase, 6)
            c = item.chunk
            scored.append((score, len(matched), c.id, replace(c, score=score)))
        scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
        return [s[3] for s in scored[:limit]]
