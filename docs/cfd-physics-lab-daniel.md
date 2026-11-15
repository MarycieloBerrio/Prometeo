# CFD Physics Lab — implementation notes (Daniel)

Branch: `feat/daniel-cfd-physics-lab`

## What was delivered

1. Reproducible OpenFOAM 11 axial annular cases for four B16 Vg values.
2. Manifests + downsampled field JSON under `data/simulations/cfd/` (separate from curated trials).
3. Backend API `/api/v1/cfd/*` + Compare Lab Physics Lab UI with Numerical Verification and
   deterministic A/B/C/D scientific interpretation.

## Scientific limits (do not dilute)

- Not a reproduction of BASS-II combustion.
- Does not invent absolute pressure.
- Does not generate Vf, temperature, or O₂ fields.
- Does not claim 0g vs 1g from isothermal forced flow.
- Mesh independence not demonstrated.

## Reproduce demo

```powershell
# API + web (from repo root)
.\init-prometeo.bat
# or: pnpm dev:api  and  pnpm --filter frontend dev
# Open /compare, select a B16 trial, scroll to CFD Physics Lab
```

Re-run CFD (optional, Docker required):

```powershell
python tools/cfd/scripts/generate_and_run.py --run
```
