"""Find the original document behind a retrieved excerpt, so the UI can show it in place."""

from __future__ import annotations

from prometeo.application.ports.outbound import SourceFile, SourceFileStore
from prometeo.domain.shared.errors import NotFoundError


class LocateSourceDocument:
    def __init__(self, files: SourceFileStore) -> None:
        self._files = files

    def execute(self, chunk_id: str) -> SourceFile:
        found = self._files.locate(chunk_id)
        if found is None:
            raise NotFoundError(
                f"No local source file for document excerpt '{chunk_id}'. Raw downloads are "
                "optional; open the cited source link instead."
            )
        return found
