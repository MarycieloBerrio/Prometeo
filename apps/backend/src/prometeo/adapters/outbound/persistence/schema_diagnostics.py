"""Read-only Postgres schema probe for Prometeo migrations 0001 + 0002.

Never ALTER/DROP/CREATE. Classifies a live database so operators know whether
`pnpm db:up` on a fresh volume is enough, or whether 0002 must be applied by hand
to an older volume (Escenario C). Migrations themselves are not modified here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

# All BASE TABLEs from 0001_init.sql. A "fresh" volume must have every one;
# checking only a subset previously let incomplete catalogs look compatible.
REQUIRED_TABLES: tuple[str, ...] = (
    "investigations",
    "investigation_relations",
    "sources",
    "assets",
    "raw_test_records",
    "trials",
    "media",
    "flame_tracks",
    "flame_track_samples",
    "measurements",
    "document_chunks",
)
REQUIRED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("assets", "remote_path"),
    ("assets", "subcategory"),
    ("sources", "source_key"),
)
REQUIRED_INDEXES: tuple[str, ...] = (
    "assets_investigation_remote_path_key",
    "sources_source_key_key",
)
LEGACY_UNIQUE_ON_PSI_RESOURCE = "assets_psi_resource_id_key"


class SchemaState(StrEnum):
    FRESH = "fresh"  # 0001 + 0002 applied
    LEGACY_PRE_KB = "legacy_pre_kb"  # 0001-era volume missing 0002 columns
    EMPTY = "empty"  # no Prometeo catalog tables
    PARTIAL = "partial"  # inconsistent / half-migrated
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    """Observable facts only — no recommendations computed here beyond classification inputs."""

    reachable: bool
    tables: frozenset[str]
    columns: frozenset[tuple[str, str]]
    indexes: frozenset[str]
    constraints: frozenset[str]
    has_vector_extension: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SchemaDiagnosis:
    state: SchemaState
    snapshot: SchemaSnapshot
    missing_tables: tuple[str, ...]
    missing_columns: tuple[tuple[str, str], ...]
    missing_indexes: tuple[str, ...]
    legacy_psi_resource_unique_present: bool
    guidance: str


class SchemaProbe(Protocol):
    def probe(self) -> SchemaSnapshot: ...


def classify(snapshot: SchemaSnapshot) -> SchemaDiagnosis:
    """Map a read-only snapshot to an actionable (but non-destructive) diagnosis."""
    if not snapshot.reachable:
        return SchemaDiagnosis(
            state=SchemaState.UNREACHABLE,
            snapshot=snapshot,
            missing_tables=REQUIRED_TABLES,
            missing_columns=REQUIRED_COLUMNS,
            missing_indexes=REQUIRED_INDEXES,
            legacy_psi_resource_unique_present=False,
            guidance=(
                "Database unreachable. Start Postgres with `pnpm db:up` (fresh volume applies "
                "0001+0002 automatically). MVP trial serving still defaults to JSON."
            ),
        )

    missing_tables = tuple(t for t in REQUIRED_TABLES if t not in snapshot.tables)
    missing_columns = tuple(c for c in REQUIRED_COLUMNS if c not in snapshot.columns)
    missing_indexes = tuple(i for i in REQUIRED_INDEXES if i not in snapshot.indexes)
    legacy_unique = LEGACY_UNIQUE_ON_PSI_RESOURCE in snapshot.constraints

    if not snapshot.tables.intersection(REQUIRED_TABLES):
        return SchemaDiagnosis(
            state=SchemaState.EMPTY,
            snapshot=snapshot,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            missing_indexes=missing_indexes,
            legacy_psi_resource_unique_present=legacy_unique,
            guidance=(
                "No Prometeo catalog tables found. Recreate with `pnpm db:up` on an empty volume, "
                "or apply `infra/db/migrations/*.sql` in order. Do not invent data."
            ),
        )

    if not missing_tables and not missing_columns and not missing_indexes and not legacy_unique:
        if not snapshot.has_vector_extension:
            return SchemaDiagnosis(
                state=SchemaState.PARTIAL,
                snapshot=snapshot,
                missing_tables=(),
                missing_columns=(),
                missing_indexes=(),
                legacy_psi_resource_unique_present=False,
                guidance=(
                    "Tables look current but the `vector` extension is missing. Install pgvector "
                    "or use the `pgvector/pgvector:pg17` image from docker-compose."
                ),
            )
        return SchemaDiagnosis(
            state=SchemaState.FRESH,
            snapshot=snapshot,
            missing_tables=(),
            missing_columns=(),
            missing_indexes=(),
            legacy_psi_resource_unique_present=False,
            guidance=(
                "Schema matches 0001+0002. Knowledge-base job may run. Trial API default remains "
                "JSON until PostgresTrialRepository is implemented."
            ),
        )

    if (
        not missing_tables
        and missing_columns
        and {"investigations", "assets", "sources"}.issubset(snapshot.tables)
    ):
        return SchemaDiagnosis(
            state=SchemaState.LEGACY_PRE_KB,
            snapshot=snapshot,
            missing_tables=(),
            missing_columns=missing_columns,
            missing_indexes=missing_indexes,
            legacy_psi_resource_unique_present=legacy_unique,
            guidance=(
                "Escenario C: volume predates knowledge-base keys. Non-destructive fix: apply "
                "`infra/db/migrations/0002_knowledge_base.sql` by hand "
                "(`docker compose exec -T db psql -U prometeo -d prometeo "
                "-f /docker-entrypoint-initdb.d/0002_knowledge_base.sql`). "
                "Destructive alternative only with explicit human approval: "
                "`docker compose down -v` then `pnpm db:up`. This tool never runs either."
            ),
        )

    return SchemaDiagnosis(
        state=SchemaState.PARTIAL,
        snapshot=snapshot,
        missing_tables=missing_tables,
        missing_columns=missing_columns,
        missing_indexes=missing_indexes,
        legacy_psi_resource_unique_present=legacy_unique,
        guidance=(
            "Partial / inconsistent schema. Inspect missing markers below. Do not edit "
            "Alejandro's migration files from an integrator hotfix; open a dedicated DB PR."
        ),
    )


class PsycopgSchemaProbe:
    """Live information_schema probe. Read-only SQL only."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def probe(self) -> SchemaSnapshot:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - env without driver
            return SchemaSnapshot(
                reachable=False,
                tables=frozenset(),
                columns=frozenset(),
                indexes=frozenset(),
                constraints=frozenset(),
                has_vector_extension=False,
                error=f"psycopg not installed: {exc}",
            )

        try:
            with (
                psycopg.connect(self._database_url, connect_timeout=3) as conn,
                conn.cursor() as cur,
            ):
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """
                )
                tables = frozenset(row[0] for row in cur.fetchall())

                cur.execute(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    """
                )
                columns = frozenset((row[0], row[1]) for row in cur.fetchall())

                cur.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    """
                )
                indexes = frozenset(row[0] for row in cur.fetchall())

                cur.execute(
                    """
                    SELECT conname
                    FROM pg_constraint
                    WHERE connamespace = 'public'::regnamespace
                    """
                )
                constraints = frozenset(row[0] for row in cur.fetchall())

                cur.execute(
                    """
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    """
                )
                has_vector = cur.fetchone() is not None
        except Exception as exc:
            # Any connectivity/SQL failure is reported as unreachable; never mutate.
            return SchemaSnapshot(
                reachable=False,
                tables=frozenset(),
                columns=frozenset(),
                indexes=frozenset(),
                constraints=frozenset(),
                has_vector_extension=False,
                error=str(exc),
            )

        return SchemaSnapshot(
            reachable=True,
            tables=tables,
            columns=columns,
            indexes=indexes,
            constraints=constraints,
            has_vector_extension=has_vector,
        )


def diagnose(database_url: str) -> SchemaDiagnosis:
    return classify(PsycopgSchemaProbe(database_url).probe())
