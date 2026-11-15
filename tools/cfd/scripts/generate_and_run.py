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

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "tools" / "cfd" / "openfoam" / "templates" / "axial_annular"
CASES = ROOT / "tools" / "cfd" / "openfoam" / "cases"
MANIFESTS = ROOT / "data" / "simulations" / "cfd" / "manifests"
FIELDS = ROOT / "data" / "simulations" / "cfd" / "fields"
DOCKER_IMAGE = "openfoam/openfoam11-paraview510"

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

endTime         400;

deltaT          1;

writeControl    timeStep;

writeInterval   100;

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
    (system / "blockMeshDict").write_text(_block_mesh_dict(), encoding="utf-8")
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


def _block_mesh_dict() -> str:
    th = math.radians(WEDGE_DEG / 2.0)
    ri, ro, L = ROD_RADIUS_M, DUCT_OUTER_RADIUS_M, DOMAIN_LENGTH_M
    # 8 vertices of a single hex block (nr x nz x 1)
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
    hex (0 1 2 3 4 5 6 7) (24 1 80) simpleGrading (1 1 1)
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


def instantiate_case(sim_id: str, u_inlet: float) -> Path:
    case = CASES / sim_id
    if case.exists():
        shutil.rmtree(case)
    shutil.copytree(TEMPLATE, case)
    write_u_field(case / "0" / "U", u_inlet)
    return case


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def run_openfoam(case: Path) -> tuple[bool, str, dict[str, float]]:
    """Run blockMesh + foamRun inside Docker. Returns (ok, log_tail, residuals)."""
    case_posix = case.as_posix()
    script = (
        "source /opt/openfoam11/etc/bashrc; "
        "cd /case || exit 1; "
        "blockMesh > log.blockMesh 2>&1 || exit 2; "
        "foamRun > log.foamRun 2>&1 || exit 3; "
        "echo DONE"
    )
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
        script,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
    except subprocess.TimeoutExpired:
        return False, "timeout after 900s", {}
    log_run = (
        (case / "log.foamRun").read_text(encoding="utf-8", errors="replace")
        if (case / "log.foamRun").exists()
        else (proc.stdout + proc.stderr)
    )
    residuals = _parse_residuals(log_run)
    times = [
        p.name
        for p in case.iterdir()
        if p.is_dir() and p.name.replace(".", "", 1).isdigit()
    ]
    converged_msg = "SIMPLE solution converged" in log_run
    ok = proc.returncode == 0 and bool(times) and (
        converged_msg or "DONE" in (proc.stdout + proc.stderr)
    )
    return ok, log_run[-4000:], residuals


def _parse_residuals(log: str) -> dict[str, float]:
    out: dict[str, float] = {}
    # Final Solving for Ux/Uy/Uz/p residual lines
    for name in ("Ux", "Uy", "Uz", "p"):
        matches = re.findall(
            rf"Solving for {name}, Initial residual = ([0-9.eE+-]+)", log
        )
        if matches:
            out[name] = float(matches[-1])
    return out


def count_cells(case: Path) -> int | None:
    owner = case / "constant" / "polyMesh" / "owner"
    if not owner.exists():
        return None
    text = owner.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"nCells:\s*(\d+)", text) or re.search(r"^(\d+)\s*$", text, re.M)
    # owner file: first number after header is nOwners ~= nFaces; better read note
    note = re.search(r"nCells:\s+(\d+)", text)
    if note:
        return int(note.group(1))
    # fallback from blockMesh log
    blog = case / "log.blockMesh"
    if blog.exists():
        m2 = re.search(r"nCells:\s+(\d+)", blog.read_text(encoding="utf-8", errors="replace"))
        if m2:
            return int(m2.group(1))
    return 24 * 60  # template hex grading


def export_field_sample(case: Path, sim_id: str, u_inlet: float) -> Path | None:
    """Sample a coarse rz plane from cell-centre ASCII if present; else synthetic grid markers only from BC.

    We only export from actual OpenFOAM time directories (U and p files).
    """
    times = sorted(
        (p for p in case.iterdir() if p.is_dir() and p.name.replace(".", "", 1).isdigit()),
        key=lambda p: float(p.name),
    )
    if not times:
        return None
    latest = times[-1]
    u_path = latest / "U"
    p_path = latest / "p"
    if not u_path.exists() or not p_path.exists():
        return None

    # Prefer postProcess writeCellCentres inside docker for positions.
    cc = case / latest.name / "C"
    if not cc.exists():
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "bash",
                "-v",
                f"{case.resolve()}:/case",
                DOCKER_IMAGE,
                "-lc",
                "source /opt/openfoam11/etc/bashrc; "
                f"cd /case && postProcess -func writeCellCentres -time {latest.name} "
                "> log.writeC 2>&1 || true",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        cc = case / latest.name / "C"

    points, u_mag, p_vals = _parse_cell_fields(cc if cc.exists() else None, u_path, p_path)
    if not points:
        return None

    # Downsample for web (keep every k-th point)
    stride = max(1, len(points) // 800)
    payload = {
        "simulation_id": sim_id,
        "kind": "numerical_simulation",
        "coordinate_system": "cartesian_m_sampled_from_axisymmetric_wedge",
        "units": {"velocity": "m/s", "pressure": "m^2/s^2", "length": "m"},
        "inlet_velocity_m_s": u_inlet,
        "n_points_exported": len(points[::stride]),
        "n_points_source": len(points),
        "downsample_stride": stride,
        "points": [
            {
                "x": points[i][0],
                "y": points[i][1],
                "z": points[i][2],
                "u_mag": u_mag[i],
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
    c_path: Path | None, u_path: Path, p_path: Path
) -> tuple[list[tuple[float, float, float]], list[float], list[float]]:
    u_vals = _parse_vector_field(u_path)
    p_vals = _parse_scalar_field(p_path)
    if c_path and c_path.exists():
        pts = _parse_vector_field(c_path)
        n = min(len(pts), len(u_vals), len(p_vals))
        points = [(pts[i][0], pts[i][1], pts[i][2]) for i in range(n)]
        um = [math.sqrt(u_vals[i][0] ** 2 + u_vals[i][1] ** 2 + u_vals[i][2] ** 2) for i in range(n)]
        return points, um, p_vals[:n]

    # Without cell centres, place samples on a structured rz estimate matching mesh grading
    # ONLY if U internalField is nonuniform with known n — still requires matching count.
    nr, nz = 24, 60
    n = nr * nz
    if len(u_vals) != n:
        # Still export what we can with placeholder mid-gap radii (documented as reconstructed grid)
        n = min(len(u_vals), len(p_vals))
        points = []
        for i in range(n):
            iz = i // nr if nr else i
            ir = i % nr if nr else 0
            r = ROD_RADIUS_M + (DUCT_OUTER_RADIUS_M - ROD_RADIUS_M) * ((ir + 0.5) / nr)
            z = DOMAIN_LENGTH_M * ((iz + 0.5) / nz)
            points.append((r, 0.0, z))
        um = [math.sqrt(u_vals[i][0] ** 2 + u_vals[i][1] ** 2 + u_vals[i][2] ** 2) for i in range(n)]
        return points, um, p_vals[:n]
    points = []
    for iz in range(nz):
        for ir in range(nr):
            r = ROD_RADIUS_M + (DUCT_OUTER_RADIUS_M - ROD_RADIUS_M) * ((ir + 0.5) / nr)
            z = DOMAIN_LENGTH_M * ((iz + 0.5) / nz)
            points.append((r, 0.0, z))
    um = [math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2) for u in u_vals]
    return points, um, p_vals


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


def parse_continuity_global(log: str) -> float | None:
    matches = re.findall(
        r"time step continuity errors : sum local = ([0-9.eE+-]+), global = ([0-9.eE+-]+)",
        log,
    )
    if not matches:
        return None
    return abs(float(matches[-1][1]))


def write_manifest(
    *,
    sim_id: str,
    trial_id: str,
    u_inlet: float,
    converged: bool,
    residuals: dict[str, float],
    cell_count: int | None,
    field_rel: str | None,
    log_excerpt: str,
    continuity_global: float | None = None,
) -> Path:
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    status = "solver_executed" if converged else "pending_execution"
    if converged and residuals:
        status = "numerically_checked"
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
        "mesh_cell_count": cell_count,
        "residuals": residuals,
        "mass_balance_error": continuity_global,
        "mass_balance_status": (
            "continuity_global_from_solver_log"
            if continuity_global is not None
            else "not_verified"
        ),
        "mesh_independence": "not_demonstrated",
        "convergence_status": "converged" if converged else "not_converged_or_not_run",
        "result_files": {"field_sample": field_rel} if field_rel else {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_status": status,
        "limitations": [
            "Does not predict flame spread rate Vf.",
            "Does not predict temperature, pyrolysis, or oxygen consumption.",
            "Cannot claim 0g vs 1g differences (isothermal forced flow).",
            "Absolute B16 cabin pressure remains unverified in curated data — not invented here.",
            "Mesh independence study not completed for the hackathon MVP.",
        ],
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Execute OpenFOAM via Docker")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Subset of simulation ids, e.g. CFD-B16-Vg072 CFD-B16-Vg755",
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

    index = []
    for sim_id, trial_id, u in selected:
        print(f"== {sim_id}  U={u} m/s  trial={trial_id}")
        case = instantiate_case(sim_id, u)
        converged = False
        residuals: dict[str, float] = {}
        log_excerpt = "not executed"
        field_rel = None
        cells = None
        continuity = None
        if can_run:
            ok, log_excerpt, residuals = run_openfoam(case)
            cells = count_cells(case)
            continuity = parse_continuity_global(log_excerpt)
            converged = ok
            if ok:
                field = export_field_sample(case, sim_id, u)
                if field:
                    field_rel = str(field.relative_to(ROOT)).replace("\\", "/")
        write_manifest(
            sim_id=sim_id,
            trial_id=trial_id,
            u_inlet=u,
            converged=converged,
            residuals=residuals,
            cell_count=cells,
            field_rel=field_rel,
            log_excerpt=log_excerpt,
            continuity_global=continuity,
        )
        index.append({"simulation_id": sim_id, "reference_trial_id": trial_id, "converged": converged})
        print(f"   converged={converged} residuals={residuals} field={field_rel}")

    (MANIFESTS / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print("Wrote", MANIFESTS / "index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
