"""Supported units mirrored from prometeo.domain.shared.quantity (do not import domain)."""

from __future__ import annotations

SUPPORTED_UNITS: frozenset[str] = frozenset(
    {
        "m",
        "cm",
        "mm",
        "um",
        "s",
        "ms",
        "min",
        "m/s",
        "cm/s",
        "mm/s",
        "kPa",
        "Pa",
        "atm",
        "psia",
        "fraction",
        "%",
        "kW",
        "W",
        "g",
        "mg",
        "kg",
        "m^2/s",
        "cm^2/s",
        "1",
    }
)

ALLOWED_QUALITY = frozenset({"measured", "derived", "extracted", "unavailable", "synthetic"})
ALLOWED_INVESTIGATION = frozenset(
    {"BASS-II", "FLEX", "SAFFIRE-I", "FLAME-SPREAD-MODELING", "SYNTHETIC"}
)
ALLOWED_GEOMETRY = frozenset({"sheet", "cylinder", "sphere", "droplet", "other"})
ALLOWED_THERMAL = frozenset({"thin", "thick", "unknown"})
ALLOWED_FLOW_DIR = frozenset({"concurrent", "opposed", "quiescent", "unknown"})
ALLOWED_PHENOMENA = frozenset({"ignition", "spread", "extinction"})
