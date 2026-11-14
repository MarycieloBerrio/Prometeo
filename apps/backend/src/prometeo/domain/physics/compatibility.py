"""Physics Validator — decides whether two trials can be compared, and why not.

A comparison isolates one or more *varied* variables; every other variable is *controlled*
and must match. Categorical mismatches (fuel, geometry, flow direction, thermal regime)
make trials not comparable; numeric mismatches beyond tolerance, or unknown controlled
values, make them partially comparable.

Unknown ≠ equal. Two missing pressures (or O₂, thickness, flow speeds) never imply a
controlled match. Relative tolerance (`DEFAULT_REL_TOL`, 5 %) is a bookkeeping heuristic
for measurement scatter — not a claim of universal physical equivalence. Near zero, the
scale is the larger absolute canonical value (see `Quantity.is_close`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from prometeo.domain.experiments.model import FlowDirection, ThermalRegime, Trial
from prometeo.domain.shared.quantity import Quantity

# Heuristic for controlled numeric "same condition" checks. Not a physical law.
# Prefer reporting PARTIAL over inventing equality when documentation is incomplete.
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

    if controlled(Variable.FUEL):
        if not a.fuel.material.strip() or not b.fuel.material.strip():
            issues.append(_warn(Variable.FUEL, "Fuel material unknown for a trial"))
        elif a.fuel.material.lower() != b.fuel.material.lower():
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
        # Opposed ≠ concurrent ≠ quiescent. Direction is independent of O₂ and of speed.
        if FlowDirection.UNKNOWN in (da, db):
            issues.append(_warn(Variable.FLOW_DIRECTION, "Flow direction unknown for a trial"))
        elif da is not db:
            issues.append(
                _blocking(
                    Variable.FLOW_DIRECTION,
                    f"{da} vs {db} (opposed/concurrent/quiescent are distinct regimes)",
                )
            )

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

    # Varied isolation: the claimed varied set must actually differ, and other essentials
    # must not also drift without being listed in `varied`.
    issues.extend(_varied_isolation_issues(a, b, varied, numeric, rel_tol))

    return CompatibilityReport(
        trial_ids=(a.id, b.id), varied=varied, level=_level(issues), issues=tuple(issues)
    )


def _varied_isolation_issues(
    a: Trial,
    b: Trial,
    varied: frozenset[Variable],
    numeric: dict[Variable, tuple[Quantity | None, Quantity | None]],
    rel_tol: float,
) -> list[CompatibilityIssue]:
    """Flag failed single-factor isolation without inventing new HTTP fields."""
    extra: list[CompatibilityIssue] = []
    if not varied:
        return extra

    for var in varied:
        if var in numeric:
            qa, qb = numeric[var]
            if qa is None or qb is None:
                extra.append(
                    CompatibilityIssue(
                        var,
                        Severity.WARNING,
                        f"Cannot isolate '{var}': value missing on one or both trials "
                        "(unknown is not a controlled level)",
                    )
                )
            elif qa.is_close(qb, rel_tol):
                extra.append(
                    CompatibilityIssue(
                        var,
                        Severity.INFO,
                        f"Varied variable '{var}' does not differ beyond {rel_tol:.0%} "
                        "relative tolerance — isolation claim is empty",
                    )
                )
        elif var is Variable.FLOW_DIRECTION:
            if (
                a.ventilation.direction is FlowDirection.UNKNOWN
                or b.ventilation.direction is FlowDirection.UNKNOWN
            ):
                extra.append(
                    CompatibilityIssue(
                        var,
                        Severity.WARNING,
                        "Cannot isolate flow_direction: direction unknown for a trial",
                    )
                )
            elif a.ventilation.direction is b.ventilation.direction:
                extra.append(
                    CompatibilityIssue(
                        var,
                        Severity.INFO,
                        "Varied flow_direction is identical on both trials",
                    )
                )
        elif var is Variable.FUEL and a.fuel.material.lower() == b.fuel.material.lower():
            extra.append(
                CompatibilityIssue(
                    var,
                    Severity.INFO,
                    "Varied fuel is identical on both trials",
                )
            )
        elif var is Variable.GEOMETRY and a.geometry.type is b.geometry.type:
            extra.append(
                CompatibilityIssue(
                    var,
                    Severity.INFO,
                    "Varied geometry is identical on both trials",
                )
            )
        elif (
            var is Variable.THERMAL_REGIME
            and a.geometry.thermal_regime is b.geometry.thermal_regime
        ):
            extra.append(
                CompatibilityIssue(
                    var,
                    Severity.INFO,
                    "Varied thermal_regime is identical on both trials",
                )
            )

    # If the user claimed a short varied set but another controlled essential also changes,
    # isolation of the intended factor is compromised (already WARNING/BLOCKING above;
    # add an explicit isolation note once).
    controlled_drift = _controlled_drift_variables(a, b, varied, numeric, rel_tol)
    if varied and controlled_drift:
        primary = next(iter(sorted(varied, key=lambda v: v.value)))
        drift_names = ", ".join(sorted(v.value for v in controlled_drift))
        extra.append(
            CompatibilityIssue(
                primary,
                Severity.WARNING,
                "Invalid single-factor isolation for "
                f"{{{', '.join(sorted(v.value for v in varied))}}}: "
                f"controlled variable(s) also differ or are unknown ({drift_names})",
            )
        )
    return extra


def _controlled_drift_variables(
    a: Trial,
    b: Trial,
    varied: frozenset[Variable],
    numeric: dict[Variable, tuple[Quantity | None, Quantity | None]],
    rel_tol: float,
) -> list[Variable]:
    drifted: list[Variable] = []
    if Variable.FUEL not in varied and a.fuel.material.lower() != b.fuel.material.lower():
        drifted.append(Variable.FUEL)
    if Variable.GEOMETRY not in varied and a.geometry.type is not b.geometry.type:
        drifted.append(Variable.GEOMETRY)
    if Variable.THERMAL_REGIME not in varied:
        ra, rb = a.geometry.thermal_regime, b.geometry.thermal_regime
        if ThermalRegime.UNKNOWN in (ra, rb) or ra is not rb:
            drifted.append(Variable.THERMAL_REGIME)
    if Variable.FLOW_DIRECTION not in varied:
        da, db = a.ventilation.direction, b.ventilation.direction
        if FlowDirection.UNKNOWN in (da, db) or da is not db:
            drifted.append(Variable.FLOW_DIRECTION)
    for var, (qa, qb) in numeric.items():
        if var in varied:
            continue
        if qa is None or qb is None or not qa.is_close(qb, rel_tol):
            drifted.append(var)
    return drifted


def _numeric_issue(
    var: Variable, qa: Quantity | None, qb: Quantity | None, rel_tol: float
) -> CompatibilityIssue | None:
    # Missing on both sides is NOT equality: the controlled factor was not documented.
    if qa is None and qb is None:
        return _warn(
            var,
            "Value unknown for both trials — unknown controlled variables are not a match "
            f"(relative tolerance {rel_tol:.0%} does not apply)",
        )
    if qa is None or qb is None:
        return _warn(var, "Value documented for only one trial")
    if qa.dimension is not qb.dimension:
        return _warn(
            var,
            f"Incompatible units/dimensions ({qa.unit} vs {qb.unit}); "
            "values cannot be treated as equal",
        )
    if not qa.is_close(qb, rel_tol):
        return _warn(
            var,
            f"{qa} vs {qb} differ by more than {rel_tol:.0%} relative "
            "(heuristic bookkeeping tolerance, not universal physical equivalence)",
        )
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
