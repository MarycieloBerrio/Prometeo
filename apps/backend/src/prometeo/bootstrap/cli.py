"""`prometeo` command-line entry point (serve the API, validate curated data, export OpenAPI)."""

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


if __name__ == "__main__":
    app()
