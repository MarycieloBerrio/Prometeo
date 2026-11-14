"""Physics Validator — decides whether two trials can be compared, and why not.

A comparison isolates one or more *varied* variables; every other variable is *controlled*
and must match. Categorical mismatches (fuel, geometry, flow direction, thermal regime)
make trials not comparable; numeric mismatches beyond tolerance, or unknown controlled
values, make them partially comparable.

Unknown ≠ equal. Two missing pressures (or O₂, thickness, flow speeds) never imply a
controlled match.

Tolerance policy:
  * Default numeric controls use `DEFAULT_REL_TOL` (5 %) as a bookkeeping heuristic —
    not universal physical equivalence (`Quantity.is_close`, scale = max(|a|,|b|)).
  * Oxygen uses an absolute band (`OXYGEN_ABS_TOL_PERCENT_POINTS`) taken from the published
    ±0.3 % O₂ note in Link et al. 2018 Fig. 7 — relative 5 % would falsely equate
    18.2 % vs 17.5 % (~3.85 % relative, 0.7 pp absolute).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from prometeo.domain.experiments.model import (
    FlowDirection,
    GeometryType,
    ThermalRegime,
    Trial,
)
from prometeo.domain.shared.quantity import Quantity

# Heuristic for non-O₂ controlled numeric "same condition" checks. Not a physical law.
DEFAULT_REL_TOL = 0.05

# Absolute O₂ match band (percentage points on the % scale). Link et al. Sci. Rep. 8:120
# (2018) Fig. 7 caption reports microgravity O₂ uncertainty of ±0.3 %. This is a published
# reporting band, not an invented instrument model. Values farther apart are not "controlled".
OXYGEN_ABS_TOL_PERCENT_POINTS = 0.3


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

    # Essential physical incompatibilities stay blocking even if listed in `varied`.
    if not a.fuel.material.strip() or not b.fuel.material.strip():
        issues.append(_warn(Variable.FUEL, "Fuel material unknown for a trial"))
    elif a.fuel.material.lower() != b.fuel.material.lower():
        issues.append(
            CompatibilityIssue(
                Variable.FUEL,
                Severity.BLOCKING,
                f"Essential fuel mismatch: {a.fuel.material} vs {b.fuel.material} "
                "(cannot be waived by listing fuel in varied)",
            )
        )

    if a.geometry.type is not b.geometry.type:
        issues.append(
            CompatibilityIssue(
                Variable.GEOMETRY,
                Severity.BLOCKING,
                f"Essential geometry mismatch: {a.geometry.type} vs {b.geometry.type} "
                "(cannot be waived by listing geometry in varied)",
            )
        )

    ra, rb = a.geometry.thermal_regime, b.geometry.thermal_regime
    if ThermalRegime.UNKNOWN in (ra, rb):
        if controlled(Variable.THERMAL_REGIME):
            issues.append(_warn(Variable.THERMAL_REGIME, "Thermal regime unknown for a trial"))
    elif ra is not rb:
        issues.append(
            CompatibilityIssue(
                Variable.THERMAL_REGIME,
                Severity.BLOCKING,
                f"Essential thermal-regime mismatch: {ra} vs {rb} "
                "(cannot be waived by listing thermal_regime in varied)",
            )
        )

    # Flow direction is an essential regime split (opposed/concurrent/quiescent).
    # Cross-regime browsing of both trial sheets remains possible in the UI; the
    # strict comparator never treats them as controlled matches via `varied`.
    da, db = a.ventilation.direction, b.ventilation.direction
    if FlowDirection.UNKNOWN in (da, db):
        if controlled(Variable.FLOW_DIRECTION):
            issues.append(_warn(Variable.FLOW_DIRECTION, "Flow direction unknown for a trial"))
    elif da is not db:
        issues.append(
            CompatibilityIssue(
                Variable.FLOW_DIRECTION,
                Severity.BLOCKING,
                f"Essential flow-direction mismatch: {da} vs {db} "
                "(opposed/concurrent/quiescent are distinct regimes; "
                "cannot be waived by listing flow_direction in varied)",
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

    if (
        a.sample_id
        and b.sample_id
        and a.sample_id == b.sample_id
        and a.id != b.id
    ):
        issues.append(
            CompatibilityIssue(
                Variable.FLOW_SPEED,
                Severity.WARNING,
                f"Same physical sample_id '{a.sample_id}': condition points from one "
                "experimental sequence, not independent replicates — descriptive series "
                "only; do not treat as statistical replication or invent uncertainty",
            )
        )

    if a.geometry.type is GeometryType.CYLINDER and b.geometry.type is GeometryType.CYLINDER:
        issues.append(
            CompatibilityIssue(
                Variable.THICKNESS,
                Severity.INFO,
                "For cylinders, geometry.thickness currently stores rod diameter "
                "(not sheet thickness); do not interpret as film thickness",
            )
        )

    issues.extend(_varied_isolation_issues(a, b, varied, numeric, rel_tol))

    return CompatibilityReport(
        trial_ids=(a.id, b.id), varied=varied, level=_level(issues), issues=tuple(issues)
    )


def oxygen_equivalent(qa: Quantity, qb: Quantity) -> bool:
    """True if O₂ mole fractions match within the published ±0.3 pp reporting band."""
    if qa.dimension is not qb.dimension:
        return False
    # Canonical fraction (0..1); band is 0.3 percentage points → 0.003 fraction.
    band = OXYGEN_ABS_TOL_PERCENT_POINTS / 100.0
    return abs(qa.canonical() - qb.canonical()) <= band


def _quantities_match(
    var: Variable, qa: Quantity, qb: Quantity, rel_tol: float
) -> bool:
    if var is Variable.OXYGEN:
        return oxygen_equivalent(qa, qb)
    return qa.is_close(qb, rel_tol)


def _varied_isolation_issues(
    a: Trial,
    b: Trial,
    varied: frozenset[Variable],
    numeric: dict[Variable, tuple[Quantity | None, Quantity | None]],
    rel_tol: float,
) -> list[CompatibilityIssue]:
    """Flag failed / empty / multi-factor isolation without inventing new HTTP fields."""
    extra: list[CompatibilityIssue] = []
    if not varied:
        return extra

    actually_differing: list[Variable] = []

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
            elif _quantities_match(var, qa, qb, rel_tol):
                # Empty experimental change → WARNING so the pair cannot stay DIRECT
                # under a false "effect of <var>" claim.
                if var is Variable.OXYGEN:
                    detail = (
                        f"Varied oxygen does not differ beyond the published "
                        f"±{OXYGEN_ABS_TOL_PERCENT_POINTS:g} percentage-point band "
                        f"({qa} vs {qb}) — no O₂ experimental change established"
                    )
                else:
                    detail = (
                        f"Varied variable '{var}' does not differ beyond the justified "
                        f"match band ({qa} vs {qb}) — no experimental change established "
                        f"for this factor"
                    )
                extra.append(CompatibilityIssue(var, Severity.WARNING, detail))
            else:
                actually_differing.append(var)
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
                        Severity.WARNING,
                        "Varied flow_direction is identical on both trials — "
                        "no experimental direction change established",
                    )
                )
            else:
                actually_differing.append(var)
        elif var is Variable.FUEL and a.fuel.material.lower() == b.fuel.material.lower():
            extra.append(
                CompatibilityIssue(
                    var,
                    Severity.WARNING,
                    "Varied fuel is identical on both trials — no fuel change established",
                )
            )
        elif var is Variable.FUEL:
            actually_differing.append(var)
        elif var is Variable.GEOMETRY and a.geometry.type is b.geometry.type:
            extra.append(
                CompatibilityIssue(
                    var,
                    Severity.WARNING,
                    "Varied geometry is identical on both trials — no geometry change established",
                )
            )
        elif var is Variable.GEOMETRY:
            actually_differing.append(var)
        elif (
            var is Variable.THERMAL_REGIME
            and a.geometry.thermal_regime is b.geometry.thermal_regime
        ):
            extra.append(
                CompatibilityIssue(
                    var,
                    Severity.WARNING,
                    "Varied thermal_regime is identical on both trials — "
                    "no regime change established",
                )
            )
        elif var is Variable.THERMAL_REGIME:
            actually_differing.append(var)

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

    if len(actually_differing) > 1:
        names = ", ".join(sorted(v.value for v in actually_differing))
        primary = actually_differing[0]
        extra.append(
            CompatibilityIssue(
                primary,
                Severity.WARNING,
                f"Multiple experimental factors differ simultaneously ({names}): "
                "not a single-factor causal isolation",
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
        if qa is None or qb is None or not _quantities_match(var, qa, qb, rel_tol):
            drifted.append(var)
    return drifted


def _numeric_issue(
    var: Variable, qa: Quantity | None, qb: Quantity | None, rel_tol: float
) -> CompatibilityIssue | None:
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
    if var is Variable.OXYGEN:
        if oxygen_equivalent(qa, qb):
            return None
        return _warn(
            var,
            f"{qa} vs {qb} differ by more than "
            f"±{OXYGEN_ABS_TOL_PERCENT_POINTS:g} percentage points "
            "(Link et al. 2018 Fig. 7 O₂ reporting band). Relative 5% tolerance is "
            "not used for oxygen — 18.2% vs 17.5% must not count as a controlled match",
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
