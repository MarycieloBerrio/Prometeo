"""Hybrid document retrieval over Postgres: full-text (tsvector) + vector (pgvector).

The two rankings are fused with Reciprocal Rank Fusion. Full-text catches exact tokens that
embeddings blur (PMMA, test ids, sample numbers); vectors catch paraphrases.

`score` is the fused rank score. It orders results and nothing more: it is not a confidence
and must never be shown as one.
"""

from __future__ import annotations

import re

import psycopg

from prometeo.adapters.outbound.persistence.postgres_knowledge_store import vector_literal
from prometeo.application.ports.outbound import DocumentChunk, TextEmbedder
from prometeo.domain.experiments.model import Provenance

_TOKEN = re.compile(r"[a-z0-9]+")
_CANDIDATES = 40  # per ranking, before fusion (matches pgvector's default hnsw.ef_search)
_RRF_K = 60

_HYBRID_SQL = """
WITH lexical AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.tsq) DESC, c.id) AS rank
    FROM document_chunks c, (SELECT to_tsquery('english', %(tsquery)s) AS tsq) q
    WHERE %(tsquery)s <> '' AND c.tsv @@ q.tsq
    ORDER BY rank
    LIMIT %(candidates)s
),
semantic AS (
    SELECT id, row_number() OVER (ORDER BY distance, id) AS rank
    FROM (
        SELECT c.id, c.embedding <=> %(vector)s::vector AS distance
        FROM document_chunks c
        WHERE c.embedding IS NOT NULL AND c.embedding_model = %(model)s
        ORDER BY c.embedding <=> %(vector)s::vector
        LIMIT %(candidates)s
    ) nearest
),
fused AS (
    SELECT id, sum(1.0 / (%(rrf_k)s + rank)) AS score
    FROM (SELECT id, rank FROM lexical UNION ALL SELECT id, rank FROM semantic) ranked
    GROUP BY id
)
SELECT c.id, c.text, c.page, c.section, s.reference, s.doi, s.url, s.source_file, s.version,
       f.score, i.code,
       ARRAY(
           SELECT related.code
           FROM (
               SELECT b.code FROM investigation_relations r
               JOIN investigations b ON b.id = r.related_id
               WHERE r.investigation_id = c.investigation_id
               UNION
               SELECT a.code FROM investigation_relations r
               JOIN investigations a ON a.id = r.investigation_id
               WHERE r.related_id = c.investigation_id
           ) related
           WHERE related.code IS NOT NULL
           ORDER BY related.code
       ) AS related_codes
FROM fused f
JOIN document_chunks c ON c.id = f.id
JOIN sources s ON s.id = c.source_id
LEFT JOIN investigations i ON i.id = c.investigation_id
ORDER BY f.score DESC, c.id
LIMIT %(limit)s
"""


class PgVectorRetriever:
    def __init__(self, dsn: str, embedder: TextEmbedder) -> None:
        self._dsn = dsn
        self._embedder = embedder

    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]:
        if not query.strip():
            return []
        params = {
            "tsquery": or_tsquery(query),
            "vector": vector_literal(self._embedder.embed_query(query)),
            "model": self._embedder.model,
            "candidates": _CANDIDATES,
            "rrf_k": _RRF_K,
            "limit": limit,
        }
        with psycopg.connect(self._dsn) as conn:
            rows = conn.execute(_HYBRID_SQL, params).fetchall()
        return [
            DocumentChunk(
                id=row[0],
                text=row[1],
                provenance=Provenance(
                    reference=f"{row[4]} [{row[3]}]" if row[3] else row[4],
                    doi=row[5],
                    url=row[6],
                    source_file=row[7],
                    page=row[2],
                    version=row[8],
                ),
                score=float(row[9]),
                investigation=row[10],
                related_investigations=tuple(row[11] or ()),
            )
            for row in rows
        ]


def or_tsquery(query: str) -> str:
    """`How does PMMA burn?` → `how | does | pmma | burn` (Postgres drops the stop words).

    Terms are OR-ed: a natural-language question rarely has every word in one chunk, and the
    ranking already rewards chunks that match more of them.
    """
    terms = list(dict.fromkeys(t for t in _TOKEN.findall(query.lower()) if len(t) > 1))
    return " | ".join(terms)
