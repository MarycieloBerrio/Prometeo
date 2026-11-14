"""KnowledgeStore backed by Postgres + pgvector (schema: infra/db/migrations).

Writes the catalog layer (investigations, sources, assets, raw_test_records) and the retrieval
layer (document_chunks). Every method is one transaction and is safe to re-run: rows are
upserted on their natural keys (`psi_accession`, `source_key`, `remote_path`).
"""

from __future__ import annotations

import mimetypes
from collections.abc import Sequence
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from prometeo.application.ports.outbound import KnowledgeChunk, KnowledgeSource, RawTableRow
from prometeo.application.use_cases.build_knowledge_base import (
    dataset_source_key,
    publication_source_key,
)
from prometeo.domain.knowledge.catalog import CatalogFile, CatalogInvestigation

_UPSERT_SOURCE = """
INSERT INTO sources (source_key, kind, evidence_role, investigation_id, reference, title,
                     authors, doi, url, source_file, version, license, retrieved_at)
VALUES (%(key)s, %(kind)s, %(role)s, %(investigation_id)s, %(reference)s, %(title)s,
        %(authors)s, %(doi)s, %(url)s, %(source_file)s, %(version)s, %(license)s, now())
ON CONFLICT (source_key) DO UPDATE SET
    kind = EXCLUDED.kind, evidence_role = EXCLUDED.evidence_role,
    investigation_id = EXCLUDED.investigation_id, reference = EXCLUDED.reference,
    title = EXCLUDED.title, authors = EXCLUDED.authors, doi = EXCLUDED.doi, url = EXCLUDED.url,
    source_file = EXCLUDED.source_file, version = EXCLUDED.version, license = EXCLUDED.license,
    retrieved_at = now()
RETURNING id
"""

_UPSERT_ASSET = """
INSERT INTO assets (investigation_id, psi_resource_id, file_name, category, subcategory,
                    media_type, size_bytes, remote_url, remote_path, psi_version)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (investigation_id, remote_path) DO UPDATE SET
    psi_resource_id = EXCLUDED.psi_resource_id, file_name = EXCLUDED.file_name,
    category = EXCLUDED.category, subcategory = EXCLUDED.subcategory,
    media_type = EXCLUDED.media_type, size_bytes = EXCLUDED.size_bytes,
    remote_url = EXCLUDED.remote_url, psi_version = EXCLUDED.psi_version
"""


class PostgresKnowledgeStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: psycopg.Connection[tuple[Any, ...]] | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── KnowledgeStore ───────────────────────────────────────────────────────────────────

    def save_investigation(self, investigation: CatalogInvestigation) -> None:
        inv = investigation
        conn = self._connection()
        with conn.transaction():
            investigation_id = self._upsert_investigation(conn, inv)
            conn.execute(
                _UPSERT_SOURCE,
                {
                    "key": dataset_source_key(inv.accession),
                    "kind": "psi_dataset",
                    "role": "experimental",
                    "investigation_id": investigation_id,
                    "reference": inv.citation,
                    "title": inv.title,
                    "authors": None,
                    "doi": inv.doi,
                    "url": inv.url,
                    "source_file": None,
                    "version": str(inv.version) if inv.version is not None else None,
                    "license": inv.license,
                },
            )
            for pub in inv.publications:
                authors = f"{pub.authors}. " if pub.authors else ""
                conn.execute(
                    _UPSERT_SOURCE,
                    {
                        "key": publication_source_key(inv.accession, pub.doi, pub.title),
                        "kind": "publication",
                        "role": "experimental",
                        "investigation_id": investigation_id,
                        "reference": f"{authors}{pub.title}",
                        "title": pub.title,
                        "authors": pub.authors,
                        "doi": pub.doi,
                        "url": f"https://doi.org/{pub.doi}" if pub.doi else None,
                        "source_file": None,
                        "version": None,
                        "license": None,
                    },
                )
            files = [*inv.files, *inv.tables]
            if files:
                with conn.cursor() as cursor:
                    cursor.executemany(
                        _UPSERT_ASSET,
                        [_asset_row(investigation_id, f) for f in files],
                    )

    def link_related(self, accession: str, related: Sequence[str]) -> None:
        conn = self._connection()
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO investigation_relations (investigation_id, related_id)
                SELECT a.id, b.id FROM investigations a, investigations b
                WHERE a.psi_accession = %s AND b.psi_accession = ANY(%s) AND a.id <> b.id
                ON CONFLICT DO NOTHING
                """,
                (accession, list(related)),
            )

    def save_table_rows(
        self, accession: str, table: CatalogFile, rows: Sequence[RawTableRow]
    ) -> None:
        conn = self._connection()
        with conn.transaction():
            investigation_id = self._investigation_id(conn, accession)
            asset_id = self._asset_id(conn, investigation_id, table)
            if asset_id is None:
                raise LookupError(f"table {table.file_name} is not catalogued for {accession}")
            # The published table is the truth: drop rows it no longer has, unless a curated
            # trial already points at them.
            conn.execute(
                """
                DELETE FROM raw_test_records r
                WHERE r.asset_id = %s AND r.row_number <> ALL(%s)
                  AND NOT EXISTS (SELECT 1 FROM trials t WHERE t.raw_record_id = r.id)
                """,
                (asset_id, [row.row_number for row in rows]),
            )
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO raw_test_records
                        (investigation_id, asset_id, row_number, test_label, data)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id, row_number) DO UPDATE SET
                        test_label = EXCLUDED.test_label, data = EXCLUDED.data
                    """,
                    [
                        (
                            investigation_id,
                            asset_id,
                            r.row_number,
                            r.test_label,
                            Jsonb(dict(r.data)),
                        )
                        for r in rows
                    ],
                )

    def record_download(
        self, accession: str, file: CatalogFile, local_path: str | None, sha256: str
    ) -> None:
        conn = self._connection()
        with conn.transaction():
            conn.execute(
                """
                UPDATE assets SET local_path = %s, sha256 = %s
                WHERE remote_path = %s
                  AND investigation_id = (SELECT id FROM investigations WHERE psi_accession = %s)
                """,
                (local_path, sha256, file.remote_path, accession),
            )

    def replace_chunks(
        self,
        accession: str,
        source: KnowledgeSource,
        chunks: Sequence[KnowledgeChunk],
        embedding_model: str,
    ) -> None:
        conn = self._connection()
        with conn.transaction():
            investigation_id = self._investigation_id(conn, accession)
            row = conn.execute(
                _UPSERT_SOURCE,
                {
                    "key": source.key,
                    "kind": source.kind,
                    "role": source.evidence_role,
                    "investigation_id": investigation_id,
                    "reference": source.reference,
                    "title": source.title,
                    "authors": None,
                    "doi": source.doi,
                    "url": source.url,
                    "source_file": source.source_file,
                    "version": source.version,
                    "license": source.license,
                },
            ).fetchone()
            assert row is not None
            source_id: int = row[0]
            asset_id = self._asset_id(conn, investigation_id, source.file) if source.file else None
            conn.execute("DELETE FROM document_chunks WHERE source_id = %s", (source_id,))
            if not chunks:
                return
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO document_chunks
                        (id, source_id, asset_id, investigation_id, chunk_index, page, section,
                         text, embedding, embedding_model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                    """,
                    [
                        (
                            c.id, source_id, asset_id, investigation_id, c.index, c.page,
                            c.section, c.text.replace("\x00", ""), vector_literal(c.embedding),
                            embedding_model,
                        )
                        for c in chunks
                    ],
                )  # fmt: skip

    # ── internals ────────────────────────────────────────────────────────────────────────

    def _connection(self) -> psycopg.Connection[tuple[Any, ...]]:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._dsn, autocommit=True)
        return self._conn

    def _upsert_investigation(
        self, conn: psycopg.Connection[tuple[Any, ...]], inv: CatalogInvestigation
    ) -> int:
        metadata = dict(inv.extra)
        if inv.research_impacts:
            metadata["researchImpacts"] = inv.research_impacts
        values = {
            "code": inv.code,
            "accession": inv.accession,
            "title": inv.title,
            "doi": inv.doi,
            "version": inv.version,
            "license": inv.license,
            "research_area": inv.research_area,
            "sub_research_area": inv.sub_research_area,
            "project_type": inv.project_type,
            "flight_platform": inv.flight_platform,
            "hardware": inv.hardware,
            "start_date": inv.start_date,
            "end_date": inv.end_date,
            "objectives": inv.objectives,
            "approach": inv.approach,
            "hypothesis": inv.hypothesis,
            "metadata": Jsonb(metadata),
        }
        # A row seeded by hand under the same code (no accession yet) is adopted, not duplicated.
        existing = conn.execute(
            """
            SELECT id FROM investigations
            WHERE psi_accession = %(accession)s OR (psi_accession IS NULL AND code = %(code)s)
            ORDER BY psi_accession IS NULL LIMIT 1
            """,
            values,
        ).fetchone()
        if existing is None:
            row = conn.execute(
                """
                INSERT INTO investigations
                    (code, psi_accession, title, doi, psi_version, license, research_area,
                     sub_research_area, project_type, flight_platform, hardware, start_date,
                     end_date, objectives, approach, hypothesis, psi_metadata, retrieved_at)
                VALUES (%(code)s, %(accession)s, %(title)s, %(doi)s, %(version)s, %(license)s,
                        %(research_area)s, %(sub_research_area)s, %(project_type)s,
                        %(flight_platform)s, %(hardware)s, %(start_date)s, %(end_date)s,
                        %(objectives)s, %(approach)s, %(hypothesis)s, %(metadata)s, now())
                RETURNING id
                """,
                values,
            ).fetchone()
            assert row is not None
            return int(row[0])
        conn.execute(
            """
            UPDATE investigations SET
                code = %(code)s, psi_accession = %(accession)s, title = %(title)s, doi = %(doi)s,
                psi_version = %(version)s, license = %(license)s,
                research_area = %(research_area)s, sub_research_area = %(sub_research_area)s,
                project_type = %(project_type)s, flight_platform = %(flight_platform)s,
                hardware = %(hardware)s, start_date = %(start_date)s, end_date = %(end_date)s,
                objectives = %(objectives)s, approach = %(approach)s,
                hypothesis = %(hypothesis)s, psi_metadata = %(metadata)s, retrieved_at = now()
            WHERE id = %(id)s
            """,
            {**values, "id": existing[0]},
        )
        return int(existing[0])

    @staticmethod
    def _investigation_id(conn: psycopg.Connection[tuple[Any, ...]], accession: str) -> int:
        row = conn.execute(
            "SELECT id FROM investigations WHERE psi_accession = %s", (accession,)
        ).fetchone()
        if row is None:
            raise LookupError(f"investigation {accession} has not been saved yet")
        return int(row[0])

    @staticmethod
    def _asset_id(
        conn: psycopg.Connection[tuple[Any, ...]], investigation_id: int, file: CatalogFile
    ) -> int | None:
        row = conn.execute(
            "SELECT id FROM assets WHERE investigation_id = %s AND remote_path = %s",
            (investigation_id, file.remote_path),
        ).fetchone()
        return int(row[0]) if row else None


def _asset_row(investigation_id: int, file: CatalogFile) -> tuple[Any, ...]:
    media_type, _ = mimetypes.guess_type(file.file_name)
    return (
        investigation_id, file.resource_id, file.file_name, file.category, file.subcategory,
        media_type, file.size_bytes, file.remote_url, file.remote_path, file.version,
    )  # fmt: skip


def vector_literal(vector: Sequence[float]) -> str:
    """pgvector text format: `[0.1,0.2,…]`."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"
