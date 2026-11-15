"""SourceFileStore adapters: where the original file of a retrieved chunk lives.

Raw downloads sit under `data/raw/` and are never in git, so a file can be missing on any
machine. Missing is a normal answer (`None`), not an error.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import psycopg

from prometeo.application.ports.outbound import SourceFile

_LOCATE_SQL = """
SELECT a.local_path, a.media_type, a.file_name
FROM document_chunks c
JOIN assets a ON a.id = c.asset_id
WHERE c.id = %s
"""


class NoSourceFiles:
    """For document stores that keep no link to an original file (the JSON keyword corpus)."""

    def locate(self, chunk_id: str) -> SourceFile | None:
        return None


class PostgresSourceFileStore:
    """Resolves a knowledge-base chunk to the downloaded PSI file it was extracted from."""

    def __init__(self, dsn: str, raw_dir: Path) -> None:
        self._dsn = dsn
        self._raw_dir = raw_dir.resolve()

    def locate(self, chunk_id: str) -> SourceFile | None:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(_LOCATE_SQL, (chunk_id,)).fetchone()
        if row is None or not row[0]:
            return None
        path = (self._raw_dir / str(row[0])).resolve()
        # `local_path` comes from the database: never serve anything outside the raw folder.
        if not path.is_relative_to(self._raw_dir) or not path.is_file():
            return None
        media_type = row[1] or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return SourceFile(path, str(media_type), str(row[2] or path.name))
