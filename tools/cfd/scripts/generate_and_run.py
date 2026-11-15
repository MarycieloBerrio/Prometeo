#!/usr/bin/env python3
"""Generate and (optionally) run Prometeo B16 axial annular OpenFOAM cases.

Uses Docker image openfoam/openfoam11-paraview510. Does NOT invent fields: if the
solver cannot run, manifests are written with validation_status=pending_execution.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from convergence import RunOutcome, classify_foam_run  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "tools" / "cfd" / "openfoam" / "templates" / "axial_annular"
CASES = ROOT / "tools" / "cfd" / "openfoam" / "cases"
MANIFESTS = ROOT / "data" / "simulations" / "cfd" / "manifests"
FIELDS = ROOT / "data" / "simulations" / "cfd" / "fields"
MESH_STUDY = ROOT / "data" / "simulations" / "cfd" / "mesh_study"
DOCKER_IMAGE = "openfoam/openfoam11-paraview510"
# Keep residualControl unchanged; only raise iteration budget so slow Uy decay can finish.
END_TIME = 5000
RESIDUAL_CONTROL_U = 1e-4
BASE_MESH = (24, 1, 80)  # nr, ntheta, nz
FINE_MESH = (48, 1, 160)

# Link et al. 2018 / curated BASS-II B16 opposed-flow condition points (published Vg).
B16_CASES = (
    ("CFD-B16-Vg072", "BASS-II-B16-Vg072", 0.0072),
    ("CFD-B16-Vg083", "BASS-II-B16-Vg083", 0.0083),
    ("CFD-B16-Vg167", "BASS-II-B16-Vg167", 0.0167),
    ("CFD-B16-Vg755", "BASS-II-B16-Vg755", 0.0755),
)

# Geometry (SI). Square 76 mm duct approximated as circular outer radius = half-width.
ROD_RADIUS_M = 0.0032  # 6.4 mm diameter
DUCT_OUTER_RADIUS_M = 0.038  # 76/2 mm — circularisation of square duct
DOMAIN_LENGTH_M = 0.12
NU_AIR_M2_S = 1.5e-5  # air ~300 K, 1 atm (White, Fluid Mechanics; isothermal assumption)
WEDGE_DEG = 5.0


def write_template_files() -> None:
    """Ensure OF11 template dictionaries exist (idempotent overwrite of generated files)."""
    system = TEMPLATE / "system"
    constant = TEMPLATE / "constant"
    zero = TEMPLATE / "0"
    system.mkdir(parents=True, exist_ok=True)
    constant.mkdir(parents=True, exist_ok=True)
    zero.mkdir(parents=True, exist_ok=True)

    (constant / "physicalProperties").write_text(
        _foam_header("dictionary", "physicalProperties")
        + "\nviscosityModel  constant;\n\n"
        f"nu              [0 2 -1 0 0 0 0] {NU_AIR_M2_S};\n\n"
        "// ************************************************************************* //\n",
        encoding="utf-8",
    )
    (constant / "momentumTransport").write_text(
        _foam_header("dictionary", "momentumTransport")
        + "\nsimulationType  laminar;\n\n"
        "// ************************************************************************* //\n",
        encoding="utf-8",
    )
    (system / "fvSchemes").write_text(
        _foam_header("dictionary", "fvSchemes")
        + """
ddtSchemes
{
    default         steadyState;
}

gradSchemes
{
    default         Gauss linear;
}

divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

// ************************************************************************* //
""",
        encoding="utf-8",
    )
    (system / "fvSolution").write_text(
        _foam_header("dictionary", "fvSolution")
        + """
solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-08;
        relTol          0.05;
        smoother        GaussSeidel;
    }

    U
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-08;
        relTol          0.1;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent      yes;
    residualControl
    {
        p               1e-4;
        U               1e-4;
    }
}

relaxationFactors
{
    equations
    {
        U               0.7;
        ".*"            0.7;
    }
}

// ************************************************************************* //
""",
        encoding="utf-8",
    )
    (system / "controlDict").write_text(
        _foam_header("dictionary", "controlDict")
        + """
application     foamRun;

solver          incompressibleFluid;

startFrom       startTime;

startTime       0;

stopAt          endTime;

endTime         5000;

deltaT          1;

writeControl    timeStep;

writeInterval   500;

purgeWrite      1;

writeFormat     ascii;

writePrecision  8;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

// ************************************************************************* //
""",
        encoding="utf-8",
    )
    (system / "blockMeshDict").write_text(_block_mesh_dict(BASE_MESH), encoding="utf-8")
    (zero / "p").write_text(
        _foam_header("volScalarField", "p")
        + """
dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{
    inlet
    {
        type            zeroGradient;
    }
    outlet
    {
        type            fixedValue;
        value           uniform 0;
    }
    rod
    {
        type            zeroGradient;
    }
    duct
    {
        type            zeroGradient;
    }
    front
    {
        type            wedge;
    }
    back
    {
        type            wedge;
    }
}

// ************************************************************************* //
""",
        encoding="utf-8",
    )


def _block_mesh_dict(mesh: tuple[int, int, int] = BASE_MESH) -> str:
    th = math.radians(WEDGE_DEG / 2.0)
    ri, ro, L = ROD_RADIUS_M, DUCT_OUTER_RADIUS_M, DOMAIN_LENGTH_M
    nr, nt, nz = mesh
    # 8 vertices of a single hex block (nr x ntheta x nz)
    verts = [
        (ri * math.cos(-th), ri * math.sin(-th), 0.0),
        (ro * math.cos(-th), ro * math.sin(-th), 0.0),
        (ro * math.cos(th), ro * math.sin(th), 0.0),
        (ri * math.cos(th), ri * math.sin(th), 0.0),
        (ri * math.cos(-th), ri * math.sin(-th), L),
        (ro * math.cos(-th), ro * math.sin(-th), L),
        (ro * math.cos(th), ro * math.sin(th), L),
        (ri * math.cos(th), ri * math.sin(th), L),
    ]
    vtxt = "\n".join(f"    ({x:.8f} {y:.8f} {z:.8f})" for x, y, z in verts)
    return (
        _foam_header("dictionary", "blockMeshDict")
        + f"""
convertToMeters 1;

vertices
(
{vtxt}
);

blocks
(
    // i = radial (rod->duct), j = circumferential (wedge, 1 cell), k = axial
    hex (0 1 2 3 4 5 6 7) ({nr} {nt} {nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    inlet
    {{
        type patch;
        faces
        (
            (0 3 2 1)
        );
    }}
    outlet
    {{
        type patch;
        faces
        (
            (4 5 6 7)
        );
    }}
    rod
    {{
        type wall;
        faces
        (
            (0 4 7 3)
        );
    }}
    duct
    {{
        type wall;
        faces
        (
            (1 2 6 5)
        );
    }}
    front
    {{
        type wedge;
        faces
        (
            (3 7 6 2)
        );
    }}
    back
    {{
        type wedge;
        faces
        (
            (0 1 5 4)
        );
    }}
);

mergePatchPairs
(
);

// ************************************************************************* //
"""
    )


def _foam_header(cls: str, obj: str) -> str:
    return f"""/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  11
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    format      ascii;
    class       {cls};
    object      {obj};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""


def write_u_field(path: Path, u_inlet: float) -> None:
    path.write_text(
        _foam_header("volVectorField", "U")
        + f"""
dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 {u_inlet});

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform (0 0 {u_inlet});
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    rod
    {{
        type            noSlip;
    }}
    duct
    {{
        type            noSlip;
    }}
    front
    {{
        type            wedge;
    }}
    back
    {{
        type            wedge;
    }}
}}

// ************************************************************************* //
""",
        encoding="utf-8",
    )


def instantiate_case(
    sim_id: str,
    u_inlet: float,
    *,
    mesh: tuple[int, int, int] = BASE_MESH,
    case_dir: Path | None = None,
) -> Path:
    case = case_dir or (CASES / sim_id)
    if case.exists():
        shutil.rmtree(case)
    shutil.copytree(TEMPLATE, case)
    (case / "system" / "blockMeshDict").write_text(_block_mesh_dict(mesh), encoding="utf-8")
    write_u_field(case / "0" / "U", u_inlet)
    return case


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _docker_bash(case: Path, script: str, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    cmd = [
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        "bash",
        "-v",
        f"{case.resolve()}:/case",
        DOCKER_IMAGE,
        "-lc",
        "source /opt/openfoam11/etc/bashrc; cd /case || exit 1; " + script,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def run_openfoam(case: Path) -> tuple[int | None, str]:
    """Run blockMesh + foamRun + checkMesh. Returns (returncode, full foamRun log).

    Echoing DONE must never be treated as residual convergence evidence.
    """
    script = (
        "blockMesh > log.blockMesh 2>&1 || exit 2; "
        "foamRun > log.foamRun 2>&1; rc=$?; "
        "checkMesh > log.checkMesh 2>&1 || true; "
        "exit $rc"
    )
    try:
        proc = _docker_bash(case, script, timeout=2400)
    except subprocess.TimeoutExpired:
        log_run = (
            (case / "log.foamRun").read_text(encoding="utf-8", errors="replace")
            if (case / "log.foamRun").exists()
            else "timeout after 2400s"
        )
        return 124, log_run
    log_run = (
        (case / "log.foamRun").read_text(encoding="utf-8", errors="replace")
        if (case / "log.foamRun").exists()
        else (proc.stdout + proc.stderr)
    )
    return proc.returncode, log_run


def parse_check_mesh(case: Path) -> dict[str, object]:
    path = case / "log.checkMesh"
    if not path.exists():
        return {"status": "not_verified", "summary": "checkMesh log missing"}
    text = path.read_text(encoding="utf-8", errors="replace")
    cells = re.search(r"cells:\s+(\d+)", text)
    points = re.search(r"points:\s+(\d+)", text)
    faces = re.search(r"faces:\s+(\d+)", text)
    max_aspect = re.search(r"Max aspect ratio = ([0-9.eE+-]+)", text)
    mesh_ok = "Mesh OK." in text
    failed = "Failed" in text and "Mesh OK." not in text
    return {
        "status": "mesh_ok" if mesh_ok else ("failed_checks" if failed else "ran"),
        "cells": int(cells.group(1)) if cells else None,
        "points": int(points.group(1)) if points else None,
        "faces": int(faces.group(1)) if faces else None,
        "max_aspect_ratio": float(max_aspect.group(1)) if max_aspect else None,
        "summary": "Mesh OK." if mesh_ok else text[-500:].strip(),
    }


def compute_patch_flow_balance(case: Path) -> dict[str, object]:
    """Integrate volumetric flux on inlet/outlet via OpenFOAM surfaceFieldValue.

    Distinct from SIMPLE continuity ``global`` residual printed each iteration.
    """
    times = _time_dirs(case)
    if not times:
        return {"status": "not_verified", "reason": "no time directories"}
    latest = times[-1].name
    for patch in ("inlet", "outlet"):
        func = (
            f"surfaceFieldValue1\n{{\n"
            f"    type            surfaceFieldValue;\n"
            f"    libs            (fieldFunctionObjects);\n"
            f"    writeControl    timeStep;\n"
            f"    writeInterval   1;\n"
            f"    log             true;\n"
            f"    writeFields     false;\n"
            f"    regionType      patch;\n"
            f"    name            {patch};\n"
            f"    operation       sum;\n"
            f"    fields          (phi);\n"
            f"}}\n"
        )
        (case / "system" / f"flowRate_{patch}").write_text(func, encoding="utf-8")
    script = (
        f"postProcess -func flowRate_inlet -time {latest} > log.flow_inlet 2>&1 || true; "
        f"postProcess -func flowRate_outlet -time {latest} > log.flow_outlet 2>&1 || true"
    )
    try:
        _docker_bash(case, script, timeout=180)
    except subprocess.TimeoutExpired:
        return {"status": "not_verified", "reason": "flowRate postProcess timeout"}

    def _read_phi(log_name: str) -> float | None:
        path = case / log_name
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        # OF11 surfaceFieldValue: "sum(inlet) of phi = <value>"
        m = re.findall(r"of phi\s*=\s*([+-]?[0-9.eE+-]+)", text)
        if not m:
            m = re.findall(r"sum\([^)]+\)\s+of\s+phi\s*=\s*([+-]?[0-9.eE+-]+)", text)
        return float(m[-1]) if m else None

    q_in = _read_phi("log.flow_inlet")
    q_out = _read_phi("log.flow_outlet")
    if q_in is None or q_out is None:
        return {
            "status": "not_verified",
            "reason": "could not parse surfaceFieldValue phi sums",
            "inlet_phi": q_in,
            "outlet_phi": q_out,
        }
    # For a closed domain, inlet flux and outlet flux should cancel (signs opposite).
    imbalance = q_in + q_out
    denom = max(abs(q_in), abs(q_out), 1e-30)
    return {
        "status": "verified_from_patch_phi",
        "inlet_phi_m3_s": q_in,
        "outlet_phi_m3_s": q_out,
        "imbalance_m3_s": imbalance,
        "relative_imbalance": abs(imbalance) / denom,
        "note": (
            "Volumetric flux sum(phi) on inlet/outlet patches. "
            "Not the same quantity as SIMPLE 'continuity errors ... global'."
        ),
    }


def count_cells(case: Path) -> int | None:
    blog = case / "log.blockMesh"
    if blog.exists():
        m2 = re.search(r"nCells:\s+(\d+)", blog.read_text(encoding="utf-8", errors="replace"))
        if m2:
            return int(m2.group(1))
    owner = case / "constant" / "polyMesh" / "owner"
    if owner.exists():
        note = re.search(
            r"nCells:\s+(\d+)", owner.read_text(encoding="utf-8", errors="replace")
        )
        if note:
            return int(note.group(1))
    return None


def _time_dirs(case: Path) -> list[Path]:
    return sorted(
        (p for p in case.iterdir() if p.is_dir() and p.name.replace(".", "", 1).isdigit()),
        key=lambda p: float(p.name),
    )


def export_field_sample(case: Path, sim_id: str, u_inlet: float) -> Path | None:
    """Export downsampled cell samples using OpenFOAM writeCellCentres coordinates only.

    If cell-centre positions cannot be obtained, fail explicitly (no reconstructed grid).
    """
    times = _time_dirs(case)
    if not times:
        print(f"   export failed: no time directories for {sim_id}", file=sys.stderr)
        return None
    latest = times[-1]
    u_path = latest / "U"
    p_path = latest / "p"
    if not u_path.exists() or not p_path.exists():
        print(f"   export failed: missing U/p in {latest}", file=sys.stderr)
        return None

    cc = case / latest.name / "C"
    if not cc.exists():
        _docker_bash(
            case,
            f"postProcess -func writeCellCentres -time {latest.name} > log.writeC 2>&1",
            timeout=180,
        )
        cc = case / latest.name / "C"
    if not cc.exists():
        print(
            f"   export failed: writeCellCentres did not produce {cc} — "
            "refusing reconstructed coordinates",
            file=sys.stderr,
        )
        return None

    parsed = _parse_cell_fields(cc, u_path, p_path)
    if parsed is None:
        print(f"   export failed: could not parse C/U/p for {sim_id}", file=sys.stderr)
        return None
    points, u_vecs, p_vals = parsed

    stride = max(1, len(points) // 800)
    payload = {
        "simulation_id": sim_id,
        "kind": "numerical_simulation",
        "coordinate_system": "cartesian_m_from_writeCellCentres",
        "units": {
            "velocity": "m/s",
            "pressure": "m^2/s^2",
            "length": "m",
        },
        "inlet_velocity_m_s": u_inlet,
        "n_points_exported": len(points[::stride]),
        "n_points_source": len(points),
        "downsample_stride": stride,
        "viewer_note": (
            "Scalar |U| samples from OpenFOAM cell centres. "
            "Vector components ux,uy,uz are exported; the web viewer plots |U| "
            "as a scalar field (no streamlines fabricated from magnitude alone)."
        ),
        "points": [
            {
                "x": points[i][0],
                "y": points[i][1],
                "z": points[i][2],
                "ux": u_vecs[i][0],
                "uy": u_vecs[i][1],
                "uz": u_vecs[i][2],
                "u_mag": math.sqrt(
                    u_vecs[i][0] ** 2 + u_vecs[i][1] ** 2 + u_vecs[i][2] ** 2
                ),
                "p": p_vals[i],
            }
            for i in range(0, len(points), stride)
        ],
    }
    FIELDS.mkdir(parents=True, exist_ok=True)
    out = FIELDS / f"{sim_id}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _parse_cell_fields(
    c_path: Path, u_path: Path, p_path: Path
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]], list[float]] | None:
    """Require verified cell-centre coordinates; never invent positions."""
    pts = _parse_vector_field(c_path)
    u_vals = _parse_vector_field(u_path)
    p_vals = _parse_scalar_field(p_path)
    if not pts or not u_vals or not p_vals:
        return None
    n = min(len(pts), len(u_vals), len(p_vals))
    if n == 0:
        return None
    return pts[:n], u_vals[:n], p_vals[:n]


def sample_probe_metrics(
    case: Path,
) -> dict[str, float] | None:
    """Defined metrics for mesh comparison: mid-gap Uz and inlet-outlet Δp."""
    times = _time_dirs(case)
    if not times:
        return None
    latest = times[-1]
    cc = latest / "C"
    if not cc.exists():
        _docker_bash(
            case,
            f"postProcess -func writeCellCentres -time {latest.name} > log.writeC 2>&1",
            timeout=180,
        )
    if not cc.exists() or not (latest / "U").exists() or not (latest / "p").exists():
        return None
    parsed = _parse_cell_fields(cc, latest / "U", latest / "p")
    if parsed is None:
        return None
    pts, u_vals, p_vals = parsed
    # Mid annular gap, mid-length cell nearest target.
    r_mid = 0.5 * (ROD_RADIUS_M + DUCT_OUTER_RADIUS_M)
    z_mid = 0.5 * DOMAIN_LENGTH_M
    best_i = min(
        range(len(pts)),
        key=lambda i: (math.hypot(pts[i][0], pts[i][1]) - r_mid) ** 2 + (pts[i][2] - z_mid) ** 2,
    )
    # Near-inlet / near-outlet mean kinematic pressure (cells in first/last 10% of length).
    inlet_p = [p_vals[i] for i, p in enumerate(pts) if p[2] <= 0.1 * DOMAIN_LENGTH_M]
    outlet_p = [p_vals[i] for i, p in enumerate(pts) if p[2] >= 0.9 * DOMAIN_LENGTH_M]
    if not inlet_p or not outlet_p:
        return None
    return {
        "uz_midgap_midspecimen_m_s": u_vals[best_i][2],
        "delta_p_inlet_minus_outlet_m2_s2": (sum(inlet_p) / len(inlet_p))
        - (sum(outlet_p) / len(outlet_p)),
    }


def _parse_vector_field(path: Path) -> list[tuple[float, float, float]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "nonuniform" not in text:
        return []
    m = re.search(
        r"internalField\s+nonuniform\s+List<vector>\s*[\r\n]+(\d+)\s*[\r\n]+\(",
        text,
    )
    if not m:
        return []
    n = int(m.group(1))
    # Match only triplets after the list header; stop before boundaryField.
    body = text[m.end() : text.find("\n)", m.end()) + 1]
    vals = re.findall(
        r"\(\s*([+-]?\d[\d.eE+-]*)\s+([+-]?\d[\d.eE+-]*)\s+([+-]?\d[\d.eE+-]*)\s*\)",
        body,
    )
    out = [(float(a), float(b), float(c)) for a, b, c in vals[:n]]
    return out


def _parse_scalar_field(path: Path) -> list[float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "nonuniform" not in text:
        return []
    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s*[\r\n]+(\d+)\s*[\r\n]+\(",
        text,
    )
    if not m:
        return []
    n = int(m.group(1))
    body = text[m.end() : text.find("\n)", m.end()) + 1]
    nums = re.findall(r"[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?", body)
    return [float(x) for x in nums[:n]]


def write_manifest(
    *,
    sim_id: str,
    trial_id: str,
    u_inlet: float,
    classified: object,
    cell_count: int | None,
    field_rel: str | None,
    log_excerpt: str,
    mesh_quality: dict[str, object] | None = None,
    patch_flow: dict[str, object] | None = None,
    mesh_independence: str = "not_demonstrated",
    mesh_resolution: tuple[int, int, int] = BASE_MESH,
) -> Path:
    from convergence import ClassifiedRun

    assert isinstance(classified, ClassifiedRun)
    MANIFESTS.mkdir(parents=True, exist_ok=True)

    patch_rel = None
    if patch_flow and patch_flow.get("status") == "verified_from_patch_phi":
        patch_rel = float(patch_flow["relative_imbalance"])  # type: ignore[arg-type]

    limitations = [
        "Does not predict flame spread rate Vf.",
        "Does not predict temperature, pyrolysis, or oxygen consumption.",
        "Cannot claim 0g vs 1g differences (isothermal forced flow).",
        "Absolute B16 cabin pressure remains unverified in curated data — not invented here.",
        "SIMPLE 'continuity errors ... global' is not a patch mass-flux balance.",
    ]
    if mesh_independence == "not_demonstrated":
        limitations.append("Mesh independence is not demonstrated for the published base mesh.")
    if classified.outcome != RunOutcome.CONVERGED:
        limitations.append(
            "Fields may exist from a finished run, but residual convergence was not announced "
            "by OpenFOAM — do not treat this case as converged."
        )

    manifest = {
        "simulation_id": sim_id,
        "reference_trial_id": trial_id,
        "result_kind": "numerical_simulation",
        "not_experimental_observation": True,
        "solver": "OpenFOAM foamRun / incompressibleFluid (SIMPLE, laminar)",
        "solver_version": "OpenFOAM 11 (Docker image openfoam/openfoam11-paraview510)",
        "model_type": "forced_laminar_isothermal_incompressible_nonreactive_axial_annular",
        "geometry": {
            "rod_diameter_m": ROD_RADIUS_M * 2,
            "rod_radius_m": ROD_RADIUS_M,
            "duct_outer_radius_m": DUCT_OUTER_RADIUS_M,
            "domain_length_m": DOMAIN_LENGTH_M,
            "wedge_degrees": WEDGE_DEG,
            "mesh_resolution_nr_ntheta_nz": list(mesh_resolution),
        },
        "geometry_assumptions": [
            "Axial flow along the rod axis (NOT cross-flow).",
            "Square 76x76 mm BASS-II duct circularised to outer radius 38 mm.",
            "Rod treated as continuous cylindrical wall along the domain (finite length and hemispherical tips not resolved).",
            "Axisymmetric wedge (5°) representation of the annular gap.",
            "Isothermal non-reactive air; no buoyancy; no O2 transport equation; no flame.",
        ],
        "inlet_velocity_m_s": u_inlet,
        "inlet_velocity_cm_s": u_inlet * 100.0,
        "oxygen_context": {
            "mole_percent": 18.2,
            "role": "experimental scenario identifier for B16 only; not solved as a species field",
        },
        "fluid_properties": {
            "nu_m2_s": NU_AIR_M2_S,
            "assumption": "constant kinematic viscosity of air ~300 K, 1 atm",
            "source": "standard air property tables (isothermal model hypothesis)",
        },
        "boundary_conditions": {
            "inlet": "fixedValue U = (0,0,Vg); p zeroGradient",
            "outlet": "U zeroGradient; p = 0",
            "rod": "noSlip",
            "duct": "noSlip",
            "front_back": "wedge",
        },
        "solver_controls": {
            "endTime": END_TIME,
            "residualControl_U": RESIDUAL_CONTROL_U,
            "residualControl_p": 1e-4,
        },
        "mesh_cell_count": cell_count,
        "mesh_quality": mesh_quality or {"status": "not_verified"},
        "residuals": classified.residuals,
        "continuity_global_abs": classified.continuity_global_abs,
        "continuity_global_note": (
            "Absolute value of OpenFOAM SIMPLE 'time step continuity errors ... global' "
            "from the final iteration — not a patch-integrated mass/volume flux balance."
        ),
        "mass_balance_error": patch_rel,
        "mass_balance_status": (
            "patch_phi_relative_imbalance"
            if patch_rel is not None
            else "not_verified"
        ),
        "patch_flow_balance": patch_flow or {"status": "not_verified"},
        "mesh_independence": mesh_independence,
        "convergence_status": classified.convergence_status,
        "solver_announced_convergence": classified.solver_announced_convergence,
        "convergence_evidence": classified.evidence,
        "result_files": (
            {"field_sample": field_rel.replace("\\", "/")} if field_rel else {}
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_status": classified.validation_status,
        "limitations": limitations,
        "provenance": {
            "reference_geometry": "Link et al., Sci. Rep. 8:120 (2018)",
            "url": "https://www.nature.com/articles/s41598-017-18398-4",
            "vg_source": "curated BASS-II B16 opposed-flow condition points / Table S1",
            "log_excerpt": log_excerpt[-1500:],
        },
    }
    out = MANIFESTS / f"{sim_id}.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def run_mesh_study(u_cases: list[tuple[str, str, float]]) -> dict[str, object]:
    """Compare BASE_MESH vs FINE_MESH for selected Vg cases without changing residualControl."""
    MESH_STUDY.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "status": "completed",
        "base_mesh": list(BASE_MESH),
        "fine_mesh": list(FINE_MESH),
        "residualControl_unchanged": True,
        "cases": {},
    }
    for sim_id, trial_id, u in u_cases:
        print(f"== mesh study {sim_id}")
        case_metrics: dict[str, object] = {}
        for label, mesh in (("base", BASE_MESH), ("fine", FINE_MESH)):
            case = instantiate_case(
                f"{sim_id}-{label}",
                u,
                mesh=mesh,
                case_dir=CASES / f"{sim_id}-{label}",
            )
            rc, log = run_openfoam(case)
            classified = classify_foam_run(
                log=log, returncode=rc, configured_end_time=float(END_TIME)
            )
            metrics = sample_probe_metrics(case)
            case_metrics[label] = {
                "mesh": list(mesh),
                "cells": count_cells(case),
                "convergence_status": classified.convergence_status,
                "evidence": classified.evidence,
                "residuals": classified.residuals,
                "metrics": metrics,
            }
            print(f"   {label}: {classified.convergence_status} metrics={metrics}")
        base_m = (case_metrics.get("base") or {}).get("metrics")  # type: ignore[union-attr]
        fine_m = (case_metrics.get("fine") or {}).get("metrics")  # type: ignore[union-attr]
        rel: dict[str, float | None] = {}
        if isinstance(base_m, dict) and isinstance(fine_m, dict):
            for key in ("uz_midgap_midspecimen_m_s", "delta_p_inlet_minus_outlet_m2_s2"):
                b, f = base_m.get(key), fine_m.get(key)
                if isinstance(b, (int, float)) and isinstance(f, (int, float)):
                    denom = max(abs(float(b)), 1e-30)
                    rel[key] = abs(float(f) - float(b)) / denom
                else:
                    rel[key] = None
        case_metrics["relative_difference_fine_vs_base"] = rel
        both_converged = (
            case_metrics["base"]["convergence_status"] == "converged"  # type: ignore[index]
            and case_metrics["fine"]["convergence_status"] == "converged"  # type: ignore[index]
        )
        case_metrics["mesh_independence"] = (
            "compared_base_vs_fine" if both_converged and rel else "not_demonstrated"
        )
        report["cases"][sim_id] = case_metrics  # type: ignore[index]
    out = MESH_STUDY / "B16_base_vs_fine.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Wrote", out)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Execute OpenFOAM via Docker")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Subset of simulation ids, e.g. CFD-B16-Vg072 CFD-B16-Vg755",
    )
    parser.add_argument(
        "--mesh-study",
        action="store_true",
        help="Also run base vs fine mesh comparison for Vg072 and Vg755",
    )
    args = parser.parse_args()

    write_template_files()
    CASES.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    FIELDS.mkdir(parents=True, exist_ok=True)

    selected = B16_CASES
    if args.only:
        wanted = set(args.only)
        selected = tuple(c for c in B16_CASES if c[0] in wanted)

    can_run = args.run and docker_available()
    if args.run and not can_run:
        print("Docker not available — writing pending manifests only", file=sys.stderr)

    mesh_independence_by_id: dict[str, str] = {}
    if can_run and args.mesh_study:
        study_cases = [c for c in selected if c[0] in {"CFD-B16-Vg072", "CFD-B16-Vg755"}]
        if not study_cases:
            study_cases = [
                c for c in B16_CASES if c[0] in {"CFD-B16-Vg072", "CFD-B16-Vg755"}
            ]
        report = run_mesh_study(study_cases)
        for sim_id, payload in (report.get("cases") or {}).items():  # type: ignore[union-attr]
            mesh_independence_by_id[sim_id] = str(
                payload.get("mesh_independence", "not_demonstrated")
            )

    index = []
    for sim_id, trial_id, u in selected:
        print(f"== {sim_id}  U={u} m/s  trial={trial_id}")
        case = instantiate_case(sim_id, u, mesh=BASE_MESH)
        log_excerpt = "not executed"
        field_rel = None
        cells = None
        mesh_quality: dict[str, object] | None = None
        patch_flow: dict[str, object] | None = None
        if can_run:
            rc, log_excerpt = run_openfoam(case)
            classified = classify_foam_run(
                log=log_excerpt, returncode=rc, configured_end_time=float(END_TIME)
            )
            cells = count_cells(case)
            mesh_quality = parse_check_mesh(case)
            # Export fields for finished runs (even if not converged) with honest status.
            if rc == 0:
                field = export_field_sample(case, sim_id, u)
                if field:
                    # Paths relative to data/ so the API (data_dir) can resolve them.
                    try:
                        field_rel = "simulations/cfd/fields/" + field.name
                    except ValueError:
                        field_rel = str(field).replace("\\", "/")
                patch_flow = compute_patch_flow_balance(case)
        else:
            classified = classify_foam_run(log="", returncode=None)

        write_manifest(
            sim_id=sim_id,
            trial_id=trial_id,
            u_inlet=u,
            classified=classified,
            cell_count=cells,
            field_rel=field_rel,
            log_excerpt=log_excerpt,
            mesh_quality=mesh_quality,
            patch_flow=patch_flow,
            mesh_independence=mesh_independence_by_id.get(sim_id, "not_demonstrated"),
            mesh_resolution=BASE_MESH,
        )
        index.append(
            {
                "simulation_id": sim_id,
                "reference_trial_id": trial_id,
                "convergence_status": classified.convergence_status,
                "validation_status": classified.validation_status,
                "field": field_rel,
            }
        )
        print(
            f"   outcome={classified.outcome.value} "
            f"validation={classified.validation_status} field={field_rel}"
        )
        print(f"   evidence: {classified.evidence}")

    (MANIFESTS / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print("Wrote", MANIFESTS / "index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
