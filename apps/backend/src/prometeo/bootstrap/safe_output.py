"""Guard CLI outputs so derived worksheets cannot overwrite curated evidence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class UnsafeOutputPathError(ValueError):
    """Raised when a requested output path would escape the allowed directory."""


def processed_root(data_dir: Path) -> Path:
    """Canonical directory for derived worksheets under ``data/processed``."""
    return (data_dir / "processed").resolve()


def resolve_processed_json_output(
    requested: Path | None,
    *,
    data_dir: Path,
    default_name: str = "bass2_flow_speeds.json",
    overwrite: bool = False,
) -> Path:
    """Resolve ``--out`` to a JSON path that must stay inside ``data/processed``.

    Rejects path traversal (``../``), absolute paths outside processed, non-JSON
    names, and (unless ``overwrite``) an existing destination. Symlinks are
    followed by ``Path.resolve``; destinations that leave processed are refused.
    """
    root = processed_root(data_dir)
    candidate = requested if requested is not None else root / default_name
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:  # pragma: no cover - platform-specific path errors
        raise UnsafeOutputPathError(f"cannot resolve output path: {candidate}") from exc

    if not _is_under(resolved, root):
        raise UnsafeOutputPathError(
            f"output must stay under {root}; refused {resolved} "
            "(derived estimates must not overwrite curated evidence)"
        )

    if resolved.suffix.lower() != ".json":
        raise UnsafeOutputPathError(f"output must be a .json worksheet; refused {resolved.name!r}")

    if resolved.exists() and not overwrite:
        raise UnsafeOutputPathError(
            f"{resolved} already exists; pass --overwrite to replace a previous "
            "derived worksheet (never curated evidence)"
        )

    return resolved


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` via a same-directory temp file, then ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.stem}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
