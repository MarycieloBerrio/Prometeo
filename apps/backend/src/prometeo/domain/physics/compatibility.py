"""Physics Validator — decides whether two trials can be compared, and why not.

A comparison isolates one or more *varied* variables; every other variable is *controlled*
and must match. Categorical mismatches (fuel, geometry, flow direction, thermal regime)
make trials not comparable; numeric mismatches beyond tolerance make them partially comparable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from prometeo.domain.experiments.model import FlowDirection, ThermalRegime, Trial
from prometeo.domain.shared.quantity import Quantity

DEFAULT_REL_TOL = 0.05


class Variable(StrEnum):
    FUEL = "fuel"
    GEOMETRY = "geometry"
    THICKNESS = "thickness"
    THERMAL_REGIME = "thermal_regime"
    OXYGEN = "oxygen"
    FLOW_SPEED = "flow_speed"
    FLOW_DIRECTION = "flow_direction"
    PRESSURE = "pressure"


class Comparability(StrEnum):
    DIRECT = "directly_comparable"
    PARTIAL = "partially_comparable"
    NOT_COMPARABLE = "not_comparable"


class Severity(StrEnum):
    BLOCKING = "blocking"  # -> NOT_COMPARABLE
    WARNING = "warning"  # -> PARTIAL
    INFO = "info"


@dataclass(frozen=True, slots=True)
class CompatibilityIssue:
    variable: Variable
    severity: Severity
    message: str


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    trial_ids: tuple[str, str]
    varied: frozenset[Variable]
    level: Comparability
    issues: tuple[CompatibilityIssue, ...] = field(default_factory=tuple)


def assess_compatibility(
    a: Trial,
    b: Trial,
    varied: frozenset[Variable],
    rel_tol: float = DEFAULT_REL_TOL,
) -> CompatibilityReport:
    issues: list[CompatibilityIssue] = []

    def controlled(v: Variable) -> bool:
        return v not in varied

    if a.is_synthetic != b.is_synthetic:
        issues.append(
            CompatibilityIssue(
                Variable.FUEL,
                Severity.BLOCKING,
                "Synthetic fixtures cannot be mixed with real data",
            )
        )
    if a.investigation is not b.investigation:
        issues.append(
            CompatibilityIssue(
                Variable.FUEL,
                Severity.WARNING,
                f"Different investigations ({a.investigation} vs {b.investigation}): "
                "facilities, scales and measurement methods differ",
            )
        )

    if controlled(Variable.FUEL) and a.fuel.material.lower() != b.fuel.material.lower():
        issues.append(_blocking(Variable.FUEL, f"{a.fuel.material} vs {b.fuel.material}"))
    if controlled(Variable.GEOMETRY) and a.geometry.type is not b.geometry.type:
        issues.append(_blocking(Variable.GEOMETRY, f"{a.geometry.type} vs {b.geometry.type}"))
    if controlled(Variable.THERMAL_REGIME):
        ra, rb = a.geometry.thermal_regime, b.geometry.thermal_regime
        if ThermalRegime.UNKNOWN in (ra, rb):
            issues.append(_warn(Variable.THERMAL_REGIME, "Thermal regime unknown for a trial"))
        elif ra is not rb:
            issues.append(_blocking(Variable.THERMAL_REGIME, f"{ra} vs {rb}"))
    if controlled(Variable.FLOW_DIRECTION):
        da, db = a.ventilation.direction, b.ventilation.direction
        if FlowDirection.UNKNOWN in (da, db):
            issues.append(_warn(Variable.FLOW_DIRECTION, "Flow direction unknown for a trial"))
        elif da is not db:
            issues.append(_blocking(Variable.FLOW_DIRECTION, f"{da} vs {db}"))

    numeric = {
        Variable.THICKNESS: (a.geometry.thickness, b.geometry.thickness),
        Variable.OXYGEN: (a.oxygen, b.oxygen),
        Variable.FLOW_SPEED: (a.ventilation.speed, b.ventilation.speed),
        Variable.PRESSURE: (a.pressure, b.pressure),
    }
    for var, (qa, qb) in numeric.items():
        if controlled(var):
            issue = _numeric_issue(var, qa, qb, rel_tol)
            if issue:
                issues.append(issue)

    return CompatibilityReport(
        trial_ids=(a.id, b.id), varied=varied, level=_level(issues), issues=tuple(issues)
    )


def _numeric_issue(
    var: Variable, qa: Quantity | None, qb: Quantity | None, rel_tol: float
) -> CompatibilityIssue | None:
    if qa is None and qb is None:
        return None
    if qa is None or qb is None:
        return _warn(var, "Value documented for only one trial")
    if not qa.is_close(qb, rel_tol):
        return _warn(var, f"{qa} vs {qb} differ by more than {rel_tol:.0%}")
    return None


def _level(issues: list[CompatibilityIssue]) -> Comparability:
    if any(i.severity is Severity.BLOCKING for i in issues):
        return Comparability.NOT_COMPARABLE
    if any(i.severity is Severity.WARNING for i in issues):
        return Comparability.PARTIAL
    return Comparability.DIRECT


def _blocking(var: Variable, detail: str) -> CompatibilityIssue:
    return CompatibilityIssue(var, Severity.BLOCKING, f"Controlled variable differs: {detail}")


def _warn(var: Variable, detail: str) -> CompatibilityIssue:
    return CompatibilityIssue(var, Severity.WARNING, detail)
