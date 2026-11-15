"""Local-environment checks behind the Windows launchers (start/init-prometeo.bat).

Run from the repo root with the backend's Python env:

    uv run --project apps/backend python tools/dev/devcheck.py env
    uv run --project apps/backend python tools/dev/devcheck.py merge-local [--yes]
    uv run --project apps/backend python tools/dev/devcheck.py deps
    uv run --project apps/backend python tools/dev/devcheck.py db

Rules: secrets (API keys, passwords, tokens) are never printed, only "set" / "not set".
Nothing here writes to the database. `merge-local` is the only command that writes a file
(the repo-root .env), always after a timestamped backup, and never replaces a value with an
empty one.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
ENV_LOCAL = ROOT / ".env.local"
ENV_EXAMPLE = ROOT / ".env.example"
BACKEND_ENV = ROOT / "apps" / "backend" / ".env"

# Every variable the stack reads, who reads it, and whether it has a built-in default.
# (backend = apps/backend/src/prometeo/bootstrap/settings.py, web = next.config.ts/gateway.ts,
#  compose = docker-compose.yml)
KNOWN: dict[str, tuple[str, str]] = {
    "PROMETEO_ENV": ("backend", "dev"),
    "PROMETEO_DATA_DIR": ("backend", "<repo>/data"),
    "PROMETEO_TRIAL_FILES": ("backend", "curated/trials.json"),
    "PROMETEO_DOCUMENT_CHUNKS_FILE": ("backend", "curated/document_chunks.json"),
    "PROMETEO_INCLUDE_SYNTHETIC": ("backend", "false"),
    "PROMETEO_TRIAL_STORE": ("backend", "json"),
    "PROMETEO_DATABASE_URL": ("backend", "postgresql://prometeo:***@localhost:5432/prometeo"),
    "PROMETEO_DOCUMENT_STORE": ("backend", "json"),
    "PROMETEO_EMBEDDING_MODEL": ("backend", "BAAI/bge-small-en-v1.5"),
    "PROMETEO_PSI_BASE_URL": ("backend", "https://psi.nasa.gov"),
    "PROMETEO_EXPLAINER": ("backend", "offline"),
    "PROMETEO_ANTHROPIC_MODEL": ("backend", "claude-sonnet-5-5"),
    "PROMETEO_ANTHROPIC_MODELS": ("backend", "claude-sonnet-5-5,claude-opus-5-5,claude-haiku-5-5"),
    "PROMETEO_ANTHROPIC_EFFORT": ("backend", "high"),
    "ANTHROPIC_API_KEY": ("backend", "<none: offline or `ant auth login`>"),
    "PROMETEO_CORS_ORIGINS": ("backend", "http://localhost:3000"),
    "PROMETEO_API_URL": ("web", "http://localhost:8000"),
    "POSTGRES_USER": ("compose", "prometeo"),
    "POSTGRES_PASSWORD": ("compose", "prometeo"),
    "POSTGRES_DB": ("compose", "prometeo"),
    "POSTGRES_PORT": ("compose", "5432"),
}
SECRET_MARKERS = ("KEY", "PASSWORD", "TOKEN", "SECRET")


def is_secret(name: str) -> bool:
    return any(marker in name.upper() for marker in SECRET_MARKERS)


def mask_url(url: str) -> str:
    """postgresql://user:pass@host/db -> postgresql://user:***@host/db."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return parts._replace(netloc=netloc).geturl()


def show(name: str, value: str) -> str:
    if is_secret(name):
        return "set" if value else "NOT SET (empty)"
    if name.endswith("DATABASE_URL"):
        return mask_url(value)
    return value


# ───────────────────────────── .env parsing ─────────────────────────────


def read_pairs(path: Path) -> list[tuple[int, str, str]]:
    """(line number, key, value) for every assignment, in file order (dotenv-style)."""
    pairs: list[tuple[int, str, str]] = []
    if not path.exists():
        return pairs
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key.replace("_", "").isalnum():
            continue
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        pairs.append((number, key, value))
    return pairs


def effective(path: Path) -> dict[str, str]:
    """Last assignment wins, as python-dotenv / pydantic-settings / docker compose read it."""
    return {key: value for _, key, value in read_pairs(path)}


def duplicates(path: Path) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = {}
    for number, key, _ in read_pairs(path):
        seen.setdefault(key, []).append(number)
    return {k: v for k, v in seen.items() if len(v) > 1}


# ───────────────────────────── env ─────────────────────────────


def config_problems(env: dict[str, str]) -> list[str]:
    """Contradictions that make the stack talk to the wrong place or fail to start."""
    problems: list[str] = []
    url = env.get("PROMETEO_DATABASE_URL", "postgresql://prometeo:prometeo@localhost:5432/prometeo")
    parts = urlsplit(url)
    port = env.get("POSTGRES_PORT", "5432")
    if parts.hostname in ("localhost", "127.0.0.1", "::1"):
        url_port = str(parts.port or 5432)
        if url_port != port:
            problems.append(
                f"POSTGRES_PORT={port} (where Docker publishes Prometeo's Postgres) but "
                f"PROMETEO_DATABASE_URL points at port {url_port}. The API would connect to a "
                "different database. Make both the same port."
            )
        for compose_key, url_value, label in (
            ("POSTGRES_USER", parts.username, "user"),
            ("POSTGRES_PASSWORD", parts.password, "password"),
            ("POSTGRES_DB", parts.path.lstrip("/"), "database name"),
        ):
            expected = env.get(compose_key, "prometeo")
            if url_value is not None and url_value != expected:
                problems.append(
                    f"The {label} in PROMETEO_DATABASE_URL differs from {compose_key}. "
                    "They must match for the local Docker database."
                )
    if env.get("PROMETEO_DOCUMENT_STORE", "json") not in ("json", "postgres"):
        problems.append("PROMETEO_DOCUMENT_STORE must be json or postgres.")
    if env.get("PROMETEO_TRIAL_STORE", "json") not in ("json", "postgres"):
        problems.append("PROMETEO_TRIAL_STORE must be json or postgres.")
    if env.get("PROMETEO_EXPLAINER", "offline") not in ("offline", "anthropic"):
        problems.append("PROMETEO_EXPLAINER must be offline or anthropic.")
    return problems


def cmd_env(_: argparse.Namespace) -> int:
    print(f"Settings file: {ENV.relative_to(ROOT)} ({'found' if ENV.exists() else 'MISSING'})")
    if not ENV.exists():
        print("  -> Run init-prometeo.bat to create it from .env.example.")
        return 1
    env = effective(ENV)
    status = 0

    print("\nVariables (value shown unless secret; '(default)' = not in .env, built-in used):")
    for name, (reader, default) in KNOWN.items():
        if name in env:
            print(f"  {name:<32} {show(name, env[name]):<55} [{reader}]")
        else:
            print(f"  {name:<32} (default) {show(name, default) if not is_secret(name) else ''}")
    unknown = sorted(k for k in env if k not in KNOWN)
    if unknown:
        print(f"\n  Not read by Prometeo (ignored): {', '.join(unknown)}")

    dups = duplicates(ENV)
    if dups:
        print("\n[WARN] Duplicate keys in .env (the LAST one wins):")
        for key, lines in dups.items():
            print(f"  - {key}: lines {', '.join(map(str, lines))}")

    for problem in config_problems(env):
        print(f"\n[ERROR] {problem}")
        status = 1

    if env.get("PROMETEO_EXPLAINER") == "anthropic" and not env.get("ANTHROPIC_API_KEY"):
        print(
            "\n[WARN] PROMETEO_EXPLAINER=anthropic but ANTHROPIC_API_KEY is empty in .env. "
            "Claude works only if you are logged in with `ant auth login`; otherwise put your "
            "own key in .env or use PROMETEO_EXPLAINER=offline."
        )

    if BACKEND_ENV.exists():
        print(
            "\n[WARN] apps/backend/.env exists. The API reads it AFTER the root .env, so its "
            "values silently win. Move what you need into the root .env and delete it."
        )

    if ENV_LOCAL.exists():
        local = effective(ENV_LOCAL)
        differing = sorted(k for k, v in local.items() if v and env.get(k) != v)
        if differing:
            print(
                "\n[WARN] .env.local is NOT read by the API or Docker, and it has values that "
                f"differ from .env: {', '.join(differing)}"
            )
            print("       To copy them into .env once (with a backup): choose 'merge' in the menu")
            print(
                "       or run:  uv run --project apps/backend python tools/dev/devcheck.py "
                "merge-local"
            )
    return status


# ───────────────────────────── merge-local ─────────────────────────────


def cmd_merge_local(args: argparse.Namespace) -> int:
    """Copy the effective values of a legacy .env.local into the root .env, once."""
    if not ENV_LOCAL.exists():
        print("No .env.local to merge.")
        return 0
    if not ENV.exists():
        source = ENV_EXAMPLE if ENV_EXAMPLE.exists() else None
        if source is None:
            print("[ERROR] Neither .env nor .env.example exists.")
            return 1
        shutil.copyfile(source, ENV)
        print("Created .env from .env.example.")

    local = effective(ENV_LOCAL)
    current = effective(ENV)
    # Never replace something with nothing; skip values already equal.
    changes = {k: v for k, v in local.items() if v and current.get(k) != v}
    if not changes:
        print(".env already has every non-empty value of .env.local. Nothing to do.")
        return 0

    print("These keys will be copied from .env.local into .env:")
    for key in sorted(changes):
        before = "(missing)" if key not in current else show(key, current[key]) or "(empty)"
        print(f"  {key:<32} {before}  ->  {show(key, changes[key])}")
    if not args.yes:
        answer = input("Apply? A backup of .env is written first. [y/N] ").strip().lower()
        if answer not in ("y", "yes", "s", "si", "sí"):
            print("Cancelled; nothing changed.")
            return 0

    backup = ENV.with_name(f".env.backup-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copyfile(ENV, backup)

    lines = ENV.read_text(encoding="utf-8-sig").splitlines()
    last_line = {key: number for number, key, _ in read_pairs(ENV)}
    pending = dict(changes)
    for key, number in last_line.items():
        if key in pending:
            lines[number - 1] = f"{key}={pending.pop(key)}"
    if pending:
        lines += ["", "# Added from .env.local by tools/dev/devcheck.py merge-local"]
        lines += [f"{key}={value}" for key, value in pending.items()]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated .env ({len(changes)} keys). Backup: {backup.name} (gitignored).")
    print(".env.local was left untouched; you can delete it once everything works.")
    return 0


# ───────────────────────────── deps ─────────────────────────────


def knowledge_deps_missing() -> list[str]:
    import importlib.util

    return [m for m in ("fastembed", "pypdf") if importlib.util.find_spec(m) is None]


def cmd_deps(_: argparse.Namespace) -> int:
    from prometeo.bootstrap.settings import get_settings

    settings = get_settings()
    missing = knowledge_deps_missing()
    if not missing:
        print("Knowledge-base packages (fastembed, pypdf): installed")
        return 0
    needed = settings.document_store == "postgres"
    level = "ERROR" if needed else "info"
    print(f"[{level}] Knowledge-base packages not installed: {', '.join(missing)}")
    if needed:
        print("  PROMETEO_DOCUMENT_STORE=postgres needs them; the Research Assistant would fail.")
    print("  Fix: init-prometeo.bat  (or: cd apps/backend; uv sync --inexact --extra knowledge)")
    return 1 if needed else 0


# ───────────────────────────── db ─────────────────────────────

EXIT_UNREACHABLE, EXIT_AUTH, EXIT_SCHEMA, EXIT_KB_EMPTY = 10, 11, 12, 13


def cmd_db(_: argparse.Namespace) -> int:
    import psycopg

    from prometeo.adapters.outbound.persistence.schema_diagnostics import SchemaState, diagnose
    from prometeo.bootstrap.settings import get_settings

    settings = get_settings()
    url = settings.database_url
    print(f"Database: {mask_url(url)}")
    print(
        f"Used by: trials={settings.trial_store}, documents={settings.document_store} "
        "(json = no database needed for that part)"
    )
    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            server = conn.execute("SHOW server_version").fetchone()
            print(f"Connection: OK (PostgreSQL {server[0] if server else '?'})")
    except psycopg.OperationalError as exc:
        message = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
        lowered = message.lower()
        if "password authentication failed" in lowered or "role" in lowered:
            print("Connection: FAILED - wrong user/password for this database.")
            print("  The Docker volume keeps the password it was created with; check that")
            print("  PROMETEO_DATABASE_URL and POSTGRES_PASSWORD in .env match it.")
            return EXIT_AUTH
        if "does not exist" in lowered and "database" in lowered:
            print("Connection: FAILED - the database name in PROMETEO_DATABASE_URL does not exist.")
            return EXIT_AUTH
        print("Connection: FAILED - nothing answering at that address/port.")
        print("  Is Postgres running? Start it with start-prometeo.bat (or: pnpm db:up).")
        return EXIT_UNREACHABLE

    report = diagnose(url)
    vector = report.snapshot.has_vector_extension
    print(f"pgvector extension: {'installed' if vector else 'MISSING'}")
    print(f"Schema (migrations 0001+0002): {report.state.value}")
    if report.state is not SchemaState.FRESH:
        if report.missing_tables:
            print(f"  missing tables: {', '.join(report.missing_tables)}")
        print(f"  {report.guidance}")
        return EXIT_SCHEMA

    with psycopg.connect(url, connect_timeout=5) as conn:

        def count(sql: str) -> int:
            row = conn.execute(sql).fetchone()
            return int(row[0]) if row else 0

        investigations = count("SELECT count(*) FROM investigations")
        sources = count("SELECT count(*) FROM sources")
        chunks = count("SELECT count(*) FROM document_chunks")
        embedded = count("SELECT count(*) FROM document_chunks WHERE embedding IS NOT NULL")
        models = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT embedding_model FROM document_chunks "
                "WHERE embedding_model IS NOT NULL"
            ).fetchall()
        ]
        trials = count("SELECT count(*) FROM trials")

    raw_psi = settings.raw_dir / "psi"
    files = sum(1 for p in raw_psi.rglob("*") if p.is_file()) if raw_psi.exists() else 0
    print(
        f"Knowledge base: {investigations} investigations, {sources} sources, "
        f"{chunks} text chunks ({embedded} with embeddings)"
    )
    print(
        f"Embedding model in DB: {', '.join(models) or '-'} (configured: "
        f"{settings.embedding_model})"
    )
    print(f"Downloaded source files in data/raw/psi: {files}")
    print(
        f"Trials table rows: {trials} (curated trials are read from JSON unless "
        "PROMETEO_TRIAL_STORE=postgres)"
    )

    if models and settings.embedding_model not in models:
        print("[WARN] The configured embedding model differs from the one used to build the KB.")
    if chunks == 0:
        print("Knowledge base is EMPTY.")
        if settings.document_store == "postgres":
            print("  PROMETEO_DOCUMENT_STORE=postgres -> the Research Assistant finds no docs.")
            print("  Build it once: double-click prometeo.bat -> option 3 (Knowledge Base).")
            return EXIT_KB_EMPTY
        print("  (Fine for now: PROMETEO_DOCUMENT_STORE=json uses the curated JSON excerpts.)")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("env", help="Check the repo-root .env (no secrets printed)")
    merge = sub.add_parser("merge-local", help="Copy .env.local values into .env (backup first)")
    merge.add_argument("--yes", action="store_true", help="Do not ask for confirmation")
    sub.add_parser("deps", help="Check knowledge-base Python packages")
    sub.add_parser("db", help="Read-only database + knowledge-base status")
    args = parser.parse_args()
    handlers = {"env": cmd_env, "merge-local": cmd_merge_local, "deps": cmd_deps, "db": cmd_db}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
