"""NASA Physical Sciences Informatics (PSI) repository client — offline ingestion only.

PSI's web app (https://psi.nasa.gov/physci/repo/search) is a JavaScript shell over a public
JSON API. Endpoints used here, checked on 2026-11-14:

  GET /geode-py/ws/repo/search?term=&from=&size=     Elasticsearch-style hits
  GET /geode-py/ws/repo/investigations/{accession}    metadata, publications, file list
  GET /geode-py/ws/studies/{accession}/download?file=&redirect=false   → presigned file URL

No login is needed for public investigations. The file list of some large investigations
(FLEX, FLEX-2, SAFFIRE-II) comes back empty from the API; those are catalogued without files.

Mapping keeps PSI's values verbatim. Empty strings become None; nothing is inferred.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

from prometeo.application.ports.outbound import DownloadedFile, KnowledgeSourceError
from prometeo.domain.knowledge.catalog import (
    CatalogFile,
    CatalogHit,
    CatalogInvestigation,
    CatalogPublication,
)

PSI_BASE_URL = "https://psi.nasa.gov"
_PAGE_SIZE = 50
_USER_AGENT = "Mozilla/5.0 (compatible; research-data-client/0.1)"

# PSI fields that have their own column/attribute; everything else scalar goes to `extra`.
_MAPPED_FIELDS = frozenset(
    {
        "accession", "title", "investigationAcronym", "doi", "version", "licenseIdentifier",
        "researchArea", "subResearchArea", "projectType", "flightProgram", "experimentHardware",
        "investigationStartDate", "investigationEndDate", "objective", "approach", "hypothesis",
        "researchImpacts", "related_glds",
    }
)  # fmt: skip


class PsiClient:
    def __init__(
        self,
        base_url: str = PSI_BASE_URL,
        *,
        cache_dir: Path | None = None,
        cache_root: Path | None = None,
        timeout_s: float = 120.0,
        retries: int = 3,
        pause_s: float = 0.5,
    ) -> None:
        """`cache_dir` keeps downloaded files (data/raw/psi); `cache_root` is what stored
        paths are made relative to (data/raw)."""
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=timeout_s,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )
        self._cache_dir = cache_dir
        self._cache_root = cache_root or cache_dir
        self._retries = retries
        self._pause_s = pause_s

    # ── InvestigationCatalog ─────────────────────────────────────────────────────────────

    def search(self, term: str) -> list[CatalogHit]:
        hits: list[CatalogHit] = []
        offset = 0
        while True:
            payload = self._get_json(
                "/geode-py/ws/repo/search", {"term": term, "from": offset, "size": _PAGE_SIZE}
            )
            try:
                page = payload["hits"]["hits"]
                total = int(payload["hits"]["total"])
            except (KeyError, TypeError, ValueError) as exc:
                raise KnowledgeSourceError(f"unexpected PSI search payload: {exc!r}") from exc
            for hit in page:
                source = hit.get("_source", {})
                accession = _text(source.get("Accession"))
                if accession:
                    hits.append(
                        CatalogHit(
                            accession=accession,
                            title=_text(source.get("Title")) or accession,
                            acronym=_text(source.get("Acronym")),
                            research_area=_text(source.get("Research Area")),
                        )
                    )
            offset += len(page)
            if not page or offset >= total:
                return hits

    def get(self, accession: str) -> CatalogInvestigation:
        payload = self._get_json(f"/geode-py/ws/repo/investigations/{accession}", {})
        return parse_investigation(payload, self._base_url)

    def download(self, accession: str, file: CatalogFile) -> DownloadedFile:
        cached = self._cache_path(accession, file)
        if cached is not None and cached.exists():
            return DownloadedFile(cached.read_bytes(), self._relative(cached))
        presigned = (
            self._request(
                "GET",
                f"/geode-py/ws/studies/{accession}/download",
                params={"file": file.file_name, "redirect": "false"},
            )
            .text.strip()
            .strip('"')
        )
        if not presigned.startswith("http"):
            raise KnowledgeSourceError(f"PSI returned no download URL for {file.file_name}")
        content = self._request("GET", presigned).content
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(content)
            return DownloadedFile(content, self._relative(cached))
        return DownloadedFile(content, None)

    def close(self) -> None:
        self._http.close()

    # ── internals ────────────────────────────────────────────────────────────────────────

    def _get_json(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        response = self._request("GET", path, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise KnowledgeSourceError(f"PSI returned non-JSON for {path}") from exc
        if not isinstance(payload, dict):
            raise KnowledgeSourceError(f"unexpected PSI payload for {path}")
        return payload

    def _request(
        self, method: str, url: str, params: Mapping[str, Any] | None = None
    ) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self._retries):
            if attempt:
                time.sleep(2.0 * attempt)
            try:
                response = self._http.request(method, url, params=params)
                if response.status_code >= 500:
                    last = KnowledgeSourceError(f"HTTP {response.status_code}")
                    continue
                response.raise_for_status()
                time.sleep(self._pause_s)  # be a polite client of a public NASA service
                return response
            except httpx.HTTPStatusError as exc:
                # Presigned URLs carry temporary credentials in the query string: never log it.
                where = url.split("?", 1)[0]
                raise KnowledgeSourceError(f"HTTP {exc.response.status_code} for {where}") from exc
            except httpx.HTTPError as exc:
                last = exc
        raise KnowledgeSourceError(f"PSI request failed after {self._retries} tries: {last!r}")

    def _cache_path(self, accession: str, file: CatalogFile) -> Path | None:
        if self._cache_dir is None:
            return None
        safe_name = "".join("_" if c in '<>:"/\\|?*' else c for c in file.file_name)
        return self._cache_dir / accession / safe_name

    def _relative(self, path: Path) -> str:
        root = self._cache_root
        try:
            return path.relative_to(root).as_posix() if root else path.as_posix()
        except ValueError:
            return path.as_posix()


# ── payload → domain (pure, unit-tested) ─────────────────────────────────────────────────


def parse_investigation(
    payload: Mapping[str, Any], base_url: str = PSI_BASE_URL
) -> CatalogInvestigation:
    accession = _text(payload.get("accession"))
    if not accession:
        raise KnowledgeSourceError("PSI investigation payload has no accession")
    related = _text(payload.get("related_glds")) or ""
    extra = {
        key: str(value).strip()
        for key, value in payload.items()
        if key not in _MAPPED_FIELDS
        and isinstance(value, (str, int, float))
        and not isinstance(value, bool)
        and str(value).strip()
    }
    return CatalogInvestigation(
        accession=accession,
        title=_text(payload.get("title")) or accession,
        url=f"{base_url.rstrip('/')}/physci/repo/data/investigations/{accession}",
        acronym=_text(payload.get("investigationAcronym")),
        doi=_text(payload.get("doi")),
        version=_int(payload.get("version")),
        license=_text(payload.get("licenseIdentifier")),
        research_area=_text(payload.get("researchArea")),
        sub_research_area=_text(payload.get("subResearchArea")),
        project_type=_text(payload.get("projectType")),
        flight_platform=_text(payload.get("flightProgram")),
        hardware=_text(payload.get("experimentHardware")),
        start_date=_date(payload.get("investigationStartDate")),
        end_date=_date(payload.get("investigationEndDate")),
        objectives=_text(payload.get("objective")),
        approach=_text(payload.get("approach")),
        hypothesis=_text(payload.get("hypothesis")),
        research_impacts=_text(payload.get("researchImpacts")),
        related_accessions=tuple(
            part for part in related.replace(";", ",").replace(" ", ",").split(",") if part
        ),
        files=tuple(_file(raw) for raw in _visible(payload.get("added"))),
        tables=tuple(
            _file(raw, category="Experimental table")
            for raw in _visible(payload.get("experimentalTable"))
        ),
        publications=tuple(
            CatalogPublication(
                title=title,
                authors=_text(pub.get("authorList")),
                doi=_text(pub.get("doi")),
                status=_text((pub.get("status") or {}).get("annotationValue")),
            )
            for pub in payload.get("publications") or []
            if isinstance(pub, dict) and (title := _text(pub.get("title")))
        ),
        extra=extra,
    )


def _visible(raw: Any) -> list[dict[str, Any]]:
    return [f for f in raw or [] if isinstance(f, dict) and f.get("visible", True)]


def _file(raw: Mapping[str, Any], category: str | None = None) -> CatalogFile:
    remote_path = _text(raw.get("remote_path")) or _text(raw.get("s3_path")) or ""
    file_name = _text(raw.get("file_name")) or remote_path.rsplit("/", 1)[-1]
    resource = raw.get("resource_id")
    size = raw.get("file_size")
    return CatalogFile(
        file_name=file_name,
        remote_path=remote_path or file_name,
        category=category or _category(remote_path),
        subcategory=_text(raw.get("subcategory")),
        size_bytes=int(size) if isinstance(size, (int, float)) else None,
        remote_url=_text(raw.get("remote_url")),
        resource_id=_text(resource.get("$oid")) if isinstance(resource, dict) else None,
        version=_int(raw.get("version")),
        restricted=bool(raw.get("restricted", False)),
    )


def _category(remote_path: str) -> str | None:
    """`/Home/psi-data/PSI-25/Reports/x.pdf` → `Reports` (the folder after the accession)."""
    parts = [p for p in remote_path.split("/") if p]
    if "psi-data" in parts:
        after = parts[parts.index("psi-data") + 1 :]
        if len(after) >= 3:  # accession / category / file
            return after[1]
    return None


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    return None


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _date(value: Any) -> date | None:
    """PSI writes investigation dates as MM-DD-YYYY. Anything else stays unknown."""
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%m-%d-%Y").date()
    except ValueError:
        return None
