# Scientific foundations and limits

Prometeo relates experimental variables. The Physics Validator does **not** require CFD.
An optional **CFD Physics Lab** (`tools/cfd/`, `data/simulations/cfd/`) may attach
**numerical_simulation** fields to B16 trial IDs; those results never replace curated
`experimental_observation` values and do not predict flame spread.

The equations below explain *which variables matter* and justify the comparability
rules in `domain/physics/compatibility.py`.

## Why microgravity is different

Without buoyancy-driven convection, oxygen transport relies on molecular diffusion and imposed
(fan) flow. Flames can stay weak and barely visible at very low flow and then intensify when
ventilation rises. A small flame does not mean the material is no longer a hazard. The response
to flow is **not monotonic**: there are flammability limits on both the low-flow and high-flow
sides.

## Governing relations (interpretive)

Oxygen species conservation:

    ∂Y_O2/∂t + u·∇Y_O2 = ∇·(D ∇Y_O2) − ω̇_O2/ρ

Energy:

    ρ c_p DT/Dt = ∇·(k ∇T) + q̇_chem − ∇·q_rad

Thermally **thin** and **thick** solids behave differently, so they are never compared directly.

## Metrics implemented (`domain/physics/metrics.py`)

| Metric | Formula | Preconditions |
|---|---|---|
| Flame spread velocity | v_f = (x_f(t₂) − x_f(t₁)) / (t₂ − t₁); least-squares fit over many points | The same physical front is tracked; spatial and temporal calibration known |
| Heat release rate (O₂ consumption) | Q̇ ≈ 13.1 kJ/g_O₂ · Δm_O₂ / Δt | O₂ consumption measured; the BASS-II report's assumptions hold |
| Péclet number | Pe = U·L / D | U, L, D defined at consistent scales for the same trial |

All functions reject wrong dimensions and invalid inputs instead of returning a number.

## FlameVision caveat

The luminous region in video is **not** necessarily the reaction front, the peak temperature or
the heat-release zone. Tracks declare `feature = luminous_leading_edge` and remain `unvalidated`
until compared with a published or reference value.

## Comparability (Physics Validator)

- The user picks the **varied** variable(s). Everything else is **controlled**.
- Controlled categorical mismatch (fuel, geometry, thermal regime, flow direction) → `not_comparable`, and deltas are withheld.
- Controlled numeric mismatch beyond 5 % (O₂, flow, pressure, thickness), unknown values, or different investigations → `partially_comparable`.
- BASS-II, FLEX and SAFFIRE are different programs with different fuels, scales and methods. They are not one statistical population.

## EvidenceRank (MVP, rule-based)

Three independent dimensions: relevance, quality/traceability and coverage. They produce the
tiers `direct`, `partial` and `insufficient`. There is **no** "% confidence" or "% safe" score
without a validated statistical model.

## CFD Physics Lab (optional numerical module)

- Solver: OpenFOAM 11 `foamRun` / `incompressibleFluid`, laminar SIMPLE, isothermal air.
- Solved: mass + momentum (velocity, kinematic pressure). **Not** solved: energy, species, pyrolysis, Vf.
- Geometry: axial annular wedge approximating the Link et al. (2018) rod-in-duct layout; square duct circularised; tips not resolved.
- Linked trial IDs: `BASS-II-B16-Vg072|083|167|755`. O₂ 18.2% is scenario context only.
- Status ladder: solver executed ≠ residual-converged (`SIMPLE solution converged`) ≠ experimentally validated model.
- `DONE` / container exit alone never implies convergence. See `tools/cfd/scripts/convergence.py`.
- Mesh independence remains **not demonstrated** unless a documented base/fine study with both converged solutions says otherwise.

## Out of scope / limitations

- No prediction for untested conditions in the MVP, and only after independent validation later.
- Non-reactive CFD must not be presented as a flame or as the cause of non-monotonic Vf(Vg).
- Microgravity does not transfer directly to partial gravity (Moon, Mars).
- Small samples do not predict full-scale fires (that is why SAFFIRE exists).
- Not a substitute for flammability testing, certification, standards or validated fire models.
