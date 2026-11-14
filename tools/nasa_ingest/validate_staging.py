#!/usr/bin/env python3
"""Validate a staging trials JSON before curated export (stdlib only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from units import (  # noqa: E402
    ALLOWED_FLOW_DIR,
    ALLOWED_GEOMETRY,
    ALLOWED_INVESTIGATION,
    ALLOWED_PHENOMENA,
    ALLOWED_QUALITY,
    ALLOWED_THERMAL,
    SUPPORTED_UNITS,
)

Json = dict[str, Any]


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _check_quantity(errors: list[str], label: str, raw: Any) -> None:
    if raw is None:
        return
    if not isinstance(raw, dict) or "value" not in raw or "unit" not in raw:
        _err(errors, f"{label}: quantity must be {{value, unit}}")
        return
    try:
        float(raw["value"])
    except (TypeError, ValueError):
        _err(errors, f"{label}: value must be numeric")
    unit = str(raw["unit"])
    if unit not in SUPPORTED_UNITS:
        _err(errors, f"{label}: unsupported unit '{unit}'")


def _traceable(prov: Json) -> bool:
    return bool(prov.get("doi") or prov.get("url") or prov.get("source_file"))


def _check_uri(errors: list[str], label: str, uri: str | None) -> None:
    if not uri:
        return
    lower = uri.lower()
    if "localhost" in lower or "127.0.0.1" in lower:
        _err(errors, f"{label}: localhost URIs are not allowed in curated evidence")
        return
    parsed = urlparse(uri)
    if label.endswith(".url") or label.endswith("media.uri"):
        if parsed.scheme not in {"http", "https"}:
            _err(errors, f"{label}: expected http(s) URL, got '{uri}'")


def validate_trials(records: list[Any], *, allow_synthetic: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(records, list):
        return ["root must be a JSON array"]

    seen: set[str] = set()
    for i, raw in enumerate(records):
        prefix = f"[{i}]"
        if not isinstance(raw, dict):
            _err(errors, f"{prefix}: trial must be an object")
            continue

        tid = raw.get("id")
        if not isinstance(tid, str) or not tid.strip():
            _err(errors, f"{prefix}: missing id")
        elif tid in seen:
            _err(errors, f"{prefix}: duplicate id '{tid}'")
        else:
            seen.add(tid)

        inv = raw.get("investigation")
        if inv not in ALLOWED_INVESTIGATION:
            _err(errors, f"{prefix}: invalid investigation '{inv}'")
        elif inv == "SYNTHETIC" and not allow_synthetic:
            _err(errors, f"{prefix}: SYNTHETIC investigation forbidden in curated staging")

        fuel = raw.get("fuel")
        if not isinstance(fuel, dict) or not fuel.get("material"):
            _err(errors, f"{prefix}: fuel.material required")

        geom = raw.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in ALLOWED_GEOMETRY:
            _err(errors, f"{prefix}: geometry.type invalid")
        else:
            _check_quantity(errors, f"{prefix}.geometry.thickness", geom.get("thickness"))
            tr = geom.get("thermal_regime", "unknown")
            if tr not in ALLOWED_THERMAL:
                _err(errors, f"{prefix}: invalid thermal_regime '{tr}'")

        _check_quantity(errors, f"{prefix}.oxygen", raw.get("oxygen"))
        ox = raw.get("oxygen")
        if isinstance(ox, dict) and "value" in ox and "unit" in ox:
            try:
                v = float(ox["value"])
                u = str(ox["unit"])
                if u == "%" and not (0 < v <= 100):
                    _err(errors, f"{prefix}: oxygen % must be in (0, 100]")
                if u == "fraction" and not (0 < v <= 1):
                    _err(errors, f"{prefix}: oxygen fraction must be in (0, 1]")
            except (TypeError, ValueError):
                pass

        vent = raw.get("ventilation") or {}
        if vent:
            if not isinstance(vent, dict):
                _err(errors, f"{prefix}: ventilation must be object")
            else:
                _check_quantity(errors, f"{prefix}.ventilation.speed", vent.get("speed"))
                spd = vent.get("speed")
                if isinstance(spd, dict) and "value" in spd:
                    try:
                        if float(spd["value"]) < 0:
                            _err(errors, f"{prefix}: flow speed cannot be negative")
                    except (TypeError, ValueError):
                        pass
                direction = vent.get("direction", "unknown")
                if direction not in ALLOWED_FLOW_DIR:
                    _err(errors, f"{prefix}: invalid flow direction '{direction}'")

        _check_quantity(errors, f"{prefix}.pressure", raw.get("pressure"))

        for p in raw.get("phenomena", []):
            if p not in ALLOWED_PHENOMENA:
                _err(errors, f"{prefix}: invalid phenomenon '{p}'")

        prov = raw.get("provenance")
        if not isinstance(prov, dict) or not prov.get("reference"):
            _err(errors, f"{prefix}: provenance.reference required")
        else:
            if not _traceable(prov):
                _err(errors, f"{prefix}: provenance needs doi, url, or source_file")
            _check_uri(errors, f"{prefix}.provenance.url", prov.get("url"))

        results = raw.get("results", [])
        if not isinstance(results, list):
            _err(errors, f"{prefix}: results must be array")
            continue
        for j, meas in enumerate(results):
            mprefix = f"{prefix}.results[{j}]"
            if not isinstance(meas, dict):
                _err(errors, f"{mprefix}: must be object")
                continue
            if not meas.get("name"):
                _err(errors, f"{mprefix}: name required")
            _check_quantity(errors, f"{mprefix}.value", meas.get("value"))
            q = meas.get("quality")
            if q not in ALLOWED_QUALITY:
                _err(errors, f"{mprefix}: invalid quality '{q}'")
            if q == "synthetic" and not allow_synthetic:
                _err(errors, f"{mprefix}: synthetic quality forbidden in curated staging")
            if q == "derived" and not meas.get("method"):
                _err(errors, f"{mprefix}: derived quality requires method")
            val = meas.get("value")
            if isinstance(val, dict) and meas.get("name") == "flame_spread_rate":
                try:
                    if float(val["value"]) < 0:
                        _err(errors, f"{mprefix}: flame_spread_rate cannot be negative")
                except (TypeError, ValueError):
                    pass
            mprov = meas.get("provenance", prov if isinstance(prov, dict) else None)
            if not isinstance(mprov, dict) or not mprov.get("reference"):
                _err(errors, f"{mprefix}: provenance.reference required")
            elif not _traceable(mprov):
                _err(errors, f"{mprefix}: provenance needs doi, url, or source_file")
            else:
                _check_uri(errors, f"{mprefix}.provenance.url", mprov.get("url"))

        for j, media in enumerate(raw.get("media", []) or []):
            mprefix = f"{prefix}.media[{j}]"
            if not isinstance(media, dict) or not media.get("uri"):
                _err(errors, f"{mprefix}: uri required")
            else:
                _check_uri(errors, f"{mprefix}.uri", str(media.get("uri")))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging", type=Path, help="Path to staging trials JSON array")
    parser.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="Allow SYNTHETIC investigation / synthetic quality (fixtures only)",
    )
    args = parser.parse_args(argv)

    try:
        records = json.loads(args.staging.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: cannot read JSON: {exc}", file=sys.stderr)
        return 2

    errors = validate_trials(records, allow_synthetic=args.allow_synthetic)
    if errors:
        print(f"FAIL: {len(errors)} issue(s) in {args.staging}")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {len(records)} trial(s) in {args.staging}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
