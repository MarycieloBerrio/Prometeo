"""Minimal keyword retriever over pre-chunked documents (JSON). MVP stand-in for
pgvector hybrid search; same `DocumentRetriever` port, so swapping is a wiring change.

Chunk file format: [{"id": str, "text": str, "provenance": {"reference": str, ...}}]
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from prometeo.application.ports.outbound import DocumentChunk
from prometeo.domain.experiments.model import Provenance

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if len(t) > 2}


class KeywordRetriever:
    def __init__(self, path: Path | None) -> None:
        self._chunks: list[DocumentChunk] = []
        if path and path.exists():
            for raw in json.loads(path.read_text(encoding="utf-8")):
                p = raw["provenance"]
                self._chunks.append(
                    DocumentChunk(
                        id=raw["id"],
                        text=raw["text"],
                        provenance=Provenance(
                            reference=p["reference"],
                            doi=p.get("doi"),
                            url=p.get("url"),
                            page=p.get("page"),
                            source_file=p.get("source_file"),
                        ),
                    )
                )

    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]:
        q = _tokens(query)
        if not q:
            return []
        scored = []
        for c in self._chunks:
            overlap = len(q & _tokens(c.text))
            if overlap:
                scored.append(
                    DocumentChunk(c.id, c.text, c.provenance, score=overlap / len(q))
                )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:limit]
