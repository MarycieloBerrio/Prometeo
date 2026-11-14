"""`prometeo` command-line entry point: serve the API, validate curated data, export OpenAPI,
build and query the knowledge base."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from prometeo.bootstrap.settings import get_settings

app = typer.Typer(help="Prometeo Evidence Engine", no_args_is_help=True)


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
    synthetic: Annotated[
        bool,
        typer.Option(help="Serve the invented fixture in data/fixtures (UI development only)."),
    ] = False,
) -> None:
    """Run the HTTP API."""
    import uvicorn

    if synthetic:
        # Set via os.environ so the uvicorn reload subprocess inherits it (works on any shell).
        os.environ["PROMETEO_TRIAL_FILES"] = "fixtures/synthetic_trials.json"
        os.environ["PROMETEO_INCLUDE_SYNTHETIC"] = "true"
        typer.secho("Serving SYNTHETIC fixture data — not NASA evidence.", fg="yellow")

    uvicorn.run("prometeo.bootstrap.api:app", host=host, port=port, reload=reload)


@app.command("validate-data")
def validate_data(
    files: Annotated[list[Path] | None, typer.Argument(help="Trial JSON files")] = None,
) -> None:
    """Parse curated trial files through the domain model; fails on unknown units/enums."""
    from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository

    paths = files or get_settings().trial_paths()
    repo = JsonTrialRepository(paths)
    trials = repo.list_all()
    synthetic = sum(t.is_synthetic for t in trials)
    typer.echo(f"OK: {len(trials)} trials ({synthetic} synthetic) from {len(paths)} file(s)")


@app.command("export-openapi")
def export_openapi(out: Path = Path("../../packages/contracts/openapi.json")) -> None:
    """Write the OpenAPI schema consumed by packages/contracts."""
    from prometeo.bootstrap.api import app as api

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(api.openapi(), indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Wrote {out}")


@app.command("build-knowledge-base")
def build_knowledge_base(
    term: Annotated[str, typer.Option(help="PSI search term.")] = "combustion",
    research_area: Annotated[
        str, typer.Option(help='Keep only this PSI research area. Pass "" to keep every hit.')
    ] = "Combustion Science",
    only: Annotated[
        list[str] | None,
        typer.Option(help="Limit to these accessions, e.g. --only PSI-25 --only PSI-26."),
    ] = None,
    documents: Annotated[
        bool, typer.Option(help="Download and index the investigations' documents.")
    ] = True,
    category: Annotated[
        list[str] | None,
        typer.Option(help="PSI document folders to index. Default: Reports, Science Documents."),
    ] = None,
    max_file_mb: Annotated[int, typer.Option(help="Skip documents larger than this.")] = 60,
) -> None:
    """Load the NASA PSI catalog into Postgres and index its text for retrieval (offline job).

    Needs the database (`pnpm db:up`) and `uv sync --extra knowledge`. Safe to re-run.
    """
    from prometeo.application.use_cases.build_knowledge_base import (
        DEFAULT_DOCUMENT_CATEGORIES,
        BuildRequest,
        DocumentStatus,
    )
    from prometeo.bootstrap.container import build_knowledge_base_job

    job = build_knowledge_base_job(get_settings())
    report = job.execute(
        BuildRequest(
            term=term,
            research_area=research_area or None,
            accessions=tuple(only or ()),
            index_documents=documents,
            document_categories=tuple(category or DEFAULT_DOCUMENT_CATEGORIES),
            max_file_bytes=max_file_mb * 1024 * 1024,
        ),
        progress=typer.echo,
    )

    typer.echo("")
    typer.echo(f"PSI search '{report.term}': {report.hits} hits")
    if report.skipped_other_area:
        typer.echo(f"Outside '{research_area}': {', '.join(report.skipped_other_area)}")
    for inv in report.investigations:
        if inv.error:
            typer.secho(f"{inv.accession:<8} FAILED: {inv.error}", fg="red")
            continue
        indexed = sum(d.status is DocumentStatus.INDEXED for d in inv.documents)
        typer.echo(
            f"{inv.accession:<8} {inv.code:<20} files={inv.files_catalogued:<5} "
            f"publications={inv.publications:<3} table_rows={inv.table_rows:<4} "
            f"chunks={inv.metadata_chunks + inv.document_chunks:<5} "
            f"documents={indexed}/{len(inv.documents)}"
        )
    not_indexed = [
        (inv.accession, d)
        for inv in report.investigations
        for d in inv.documents
        if d.status is not DocumentStatus.INDEXED
    ]
    if not_indexed:
        typer.echo("")
        typer.echo("Documents NOT indexed:")
        for accession, doc in not_indexed:
            detail = f" ({doc.detail})" if doc.detail else ""
            typer.echo(f"  {accession:<8} {doc.status.value}{detail}: {doc.file_name}")
    typer.echo("")
    typer.echo(f"Total: {report.total_chunks} chunks, embedded with {report.embedding_model}")
    if report.failed:
        raise typer.Exit(code=1)


@app.command("diagnose-db")
def diagnose_db() -> None:
    """Read-only check of Postgres schema vs migrations 0001+0002 (never mutates the DB)."""
    from prometeo.adapters.outbound.persistence.schema_diagnostics import (
        SchemaState,
        diagnose,
    )

    settings = get_settings()
    report = diagnose(settings.database_url)
    color = {
        SchemaState.FRESH: "green",
        SchemaState.LEGACY_PRE_KB: "yellow",
        SchemaState.EMPTY: "yellow",
        SchemaState.PARTIAL: "red",
        SchemaState.UNREACHABLE: "yellow",
    }[report.state]

    typer.secho(f"state: {report.state.value}", fg=color, bold=True)
    if report.snapshot.error:
        typer.echo(f"error: {report.snapshot.error}")
    if report.missing_tables:
        typer.echo(f"missing tables: {', '.join(report.missing_tables)}")
    if report.missing_columns:
        cols = ", ".join(f"{t}.{c}" for t, c in report.missing_columns)
        typer.echo(f"missing columns: {cols}")
    if report.missing_indexes:
        typer.echo(f"missing indexes: {', '.join(report.missing_indexes)}")
    if report.legacy_psi_resource_unique_present:
        typer.echo("legacy constraint still present: assets_psi_resource_id_key")
    typer.echo(report.guidance)
    if report.state in {SchemaState.PARTIAL}:
        raise typer.Exit(code=1)


@app.command("search-knowledge-base")
def search_knowledge_base(
    query: Annotated[str, typer.Argument(help="Question or keywords.")],
    limit: int = 5,
) -> None:
    """Run a hybrid (full-text + vector) search against the knowledge base in Postgres."""
    from prometeo.bootstrap.container import document_retriever

    settings = get_settings().model_copy(update={"document_store": "postgres"})
    results = document_retriever(settings).retrieve(query, limit=limit)
    if not results:
        typer.echo("No recorded evidence matches this query.")
        return
    for position, chunk in enumerate(results, start=1):
        page = f", p. {chunk.provenance.page}" if chunk.provenance.page else ""
        typer.secho(f"{position}. {chunk.provenance.reference}{page}", bold=True)
        typer.echo(f"   {chunk.provenance.url or ''}")
        typer.echo(f"   {chunk.text[:300]}{'…' if len(chunk.text) > 300 else ''}")
        typer.echo("")


if __name__ == "__main__":
    app()
