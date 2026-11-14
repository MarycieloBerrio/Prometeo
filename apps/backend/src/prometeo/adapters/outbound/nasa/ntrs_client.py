"""NASA Technical Reports Server (NTRS) client — used by offline ingestion, not per request.

Returns raw citation metadata; mapping into curated trials is a reviewed, human-in-the-loop
step (see data/README.md). Verify endpoint shape against https://ntrs.nasa.gov/api before use.
"""

from __future__ import annotations

from typing import Any

import httpx

NTRS_BASE_URL = "https://ntrs.nasa.gov/api"


class NtrsClient:
    def __init__(self, base_url: str = NTRS_BASE_URL, timeout_s: float = 30.0) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=timeout_s)

    def search(self, query: str, page_size: int = 25) -> list[dict[str, Any]]:
        resp = self._http.get("/citations/search", params={"q": query, "page.size": page_size})
        resp.raise_for_status()
        results: list[dict[str, Any]] = resp.json().get("results", [])
        return results

    def close(self) -> None:
        self._http.close()
