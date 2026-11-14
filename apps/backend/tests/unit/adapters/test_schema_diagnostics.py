"""Unit tests for read-only schema classification (no live Postgres required)."""

from __future__ import annotations

from prometeo.adapters.outbound.persistence.schema_diagnostics import (
    LEGACY_UNIQUE_ON_PSI_RESOURCE,
    REQUIRED_COLUMNS,
    REQUIRED_INDEXES,
    REQUIRED_TABLES,
    SchemaSnapshot,
    SchemaState,
    classify,
)


def _snap(
    *,
    reachable: bool = True,
    tables: frozenset[str] | None = None,
    columns: frozenset[tuple[str, str]] | None = None,
    indexes: frozenset[str] | None = None,
    constraints: frozenset[str] | None = None,
    has_vector_extension: bool = True,
    error: str | None = None,
) -> SchemaSnapshot:
    return SchemaSnapshot(
        reachable=reachable,
        tables=tables or frozenset(),
        columns=columns or frozenset(),
        indexes=indexes or frozenset(),
        constraints=constraints or frozenset(),
        has_vector_extension=has_vector_extension,
        error=error,
    )


def test_unreachable() -> None:
    diagnosis = classify(_snap(reachable=False, error="connection refused"))
    assert diagnosis.state is SchemaState.UNREACHABLE
    assert "pnpm db:up" in diagnosis.guidance


def test_empty() -> None:
    diagnosis = classify(_snap(tables=frozenset({"unrelated"})))
    assert diagnosis.state is SchemaState.EMPTY


def test_fresh() -> None:
    diagnosis = classify(
        _snap(
            tables=frozenset(REQUIRED_TABLES),
            columns=frozenset(REQUIRED_COLUMNS),
            indexes=frozenset(REQUIRED_INDEXES),
        )
    )
    assert diagnosis.state is SchemaState.FRESH
    assert diagnosis.missing_tables == ()
    assert diagnosis.missing_columns == ()


def test_legacy_pre_kb() -> None:
    diagnosis = classify(
        _snap(
            tables=frozenset(REQUIRED_TABLES),
            columns=frozenset(),
            indexes=frozenset(),
            constraints=frozenset({LEGACY_UNIQUE_ON_PSI_RESOURCE}),
        )
    )
    assert diagnosis.state is SchemaState.LEGACY_PRE_KB
    assert diagnosis.legacy_psi_resource_unique_present
    assert "0002_knowledge_base.sql" in diagnosis.guidance
    assert "down -v" in diagnosis.guidance
    assert "never runs" in diagnosis.guidance.lower()


def test_partial_missing_vector() -> None:
    diagnosis = classify(
        _snap(
            tables=frozenset(REQUIRED_TABLES),
            columns=frozenset(REQUIRED_COLUMNS),
            indexes=frozenset(REQUIRED_INDEXES),
            has_vector_extension=False,
        )
    )
    assert diagnosis.state is SchemaState.PARTIAL
    assert "vector" in diagnosis.guidance.lower()


def test_partial_when_subset_of_catalog_tables_present() -> None:
    """Six-table catalogs must not classify as fresh (Ciclo 9 harden)."""
    subset = frozenset(
        {
            "investigations",
            "sources",
            "assets",
            "trials",
            "measurements",
            "document_chunks",
        }
    )
    diagnosis = classify(
        _snap(
            tables=subset,
            columns=frozenset(REQUIRED_COLUMNS),
            indexes=frozenset(REQUIRED_INDEXES),
        )
    )
    assert diagnosis.state is SchemaState.PARTIAL
    assert "media" in diagnosis.missing_tables
    assert "flame_tracks" in diagnosis.missing_tables
    assert len(REQUIRED_TABLES) == 11


def test_required_tables_match_0001_init_count() -> None:
    assert len(REQUIRED_TABLES) == 11
    assert "investigation_relations" in REQUIRED_TABLES
    assert "raw_test_records" in REQUIRED_TABLES
    assert "flame_track_samples" in REQUIRED_TABLES
