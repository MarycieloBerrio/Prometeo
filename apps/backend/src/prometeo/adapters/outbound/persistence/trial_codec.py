"""JSON <-> domain mapping for curated trial records (see data/README.md for the schema)."""

from __future__ import annotations

from typing import Any

from prometeo.domain.experiments.model import (
    DataQuality,
    FlowDirection,
    Fuel,
    Geometry,
    GeometryType,
    Investigation,
    Measurement,
    MediaRef,
    Phenomenon,
    Provenance,
    ThermalRegime,
    Trial,
    Ventilation,
)
from prometeo.domain.shared.quantity import Quantity

Json = dict[str, Any]


def _q(raw: Json | None) -> Quantity | None:
    return None if raw is None else Quantity(float(raw["value"]), str(raw["unit"]))


def _prov(raw: Json) -> Provenance:
    return Provenance(
        reference=raw["reference"],
        source_file=raw.get("source_file"),
        doi=raw.get("doi"),
        url=raw.get("url"),
        page=raw.get("page"),
        version=raw.get("version"),
    )


def trial_from_json(raw: Json) -> Trial:
    geom = raw["geometry"]
    vent = raw.get("ventilation", {})
    trial_prov = _prov(raw["provenance"])
    return Trial(
        id=raw["id"],
        investigation=Investigation(raw["investigation"]),
        sample_id=raw.get("sample_id"),
        fuel=Fuel(raw["fuel"]["material"], raw["fuel"].get("composition")),
        geometry=Geometry(
            GeometryType(geom["type"]),
            _q(geom.get("thickness")),
            ThermalRegime(geom.get("thermal_regime", "unknown")),
        ),
        oxygen=_q(raw.get("oxygen")),
        ventilation=Ventilation(
            _q(vent.get("speed")), FlowDirection(vent.get("direction", "unknown"))
        ),
        pressure=_q(raw.get("pressure")),
        phenomena=frozenset(Phenomenon(p) for p in raw.get("phenomena", [])),
        provenance=trial_prov,
        results=tuple(
            Measurement(
                name=r["name"],
                value=Quantity(float(r["value"]["value"]), str(r["value"]["unit"])),
                quality=DataQuality(r["quality"]),
                provenance=_prov(r["provenance"]) if "provenance" in r else trial_prov,
                uncertainty=_q(r.get("uncertainty")),
                method=r.get("method"),
            )
            for r in raw.get("results", [])
        ),
        media=tuple(
            MediaRef(m["kind"], m["uri"], m.get("start_s"), m.get("end_s"))
            for m in raw.get("media", [])
        ),
        notes=raw.get("notes"),
        tags=frozenset(raw.get("tags", [])),
    )
