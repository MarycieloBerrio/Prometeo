"use client";

import type { CfdSimulation } from "@/domain/cfd";

/** Shows only metrics present in the CFD manifest — never invents PASS. */
export function NumericalVerificationPanel({ simulation }: { simulation: CfdSimulation }) {
  const residualEntries = Object.entries(simulation.residuals);
  return (
    <section className="cfd-verify" aria-label="Numerical Verification">
      <h4>Numerical Verification</h4>
      <p className="muted">
        Distinguishes solver execution, residual convergence announced by OpenFOAM, and
        experimental model validation — these are not equivalent.
      </p>
      <table>
        <tbody>
          <Row label="Solver" value={`${simulation.solver}`} />
          <Row label="Solver version" value={simulation.solver_version} />
          <Row label="Model type" value={simulation.model_type} />
          <Row
            label="Mesh cells"
            value={
              simulation.mesh_cell_count != null
                ? String(simulation.mesh_cell_count)
                : "not verified"
            }
          />
          <Row
            label="Mesh quality (checkMesh)"
            value={simulation.mesh_quality_status ?? "not verified"}
          />
          <Row
            label="Residuals (final initial)"
            value={
              residualEntries.length > 0
                ? residualEntries.map(([k, v]) => `${k}=${v.toExponential(3)}`).join(" · ")
                : "not verified"
            }
          />
          <Row label="Convergence status" value={simulation.convergence_status} />
          <Row
            label="OpenFOAM announced convergence"
            value={simulation.solver_announced_convergence ? "yes" : "no"}
          />
          <Row
            label="Convergence evidence"
            value={simulation.convergence_evidence || "not verified"}
          />
          <Row
            label="Patch mass/volume flux balance"
            value={
              simulation.mass_balance_error != null
                ? `relative imbalance ${simulation.mass_balance_error.toExponential(3)} (${simulation.mass_balance_status})`
                : "not verified"
            }
          />
          <Row
            label="SIMPLE continuity global (log)"
            value={
              simulation.continuity_global_abs != null
                ? `${simulation.continuity_global_abs.toExponential(3)} (not a patch flux balance)`
                : "not verified"
            }
          />
          <Row label="Mesh independence" value={simulation.mesh_independence} />
          <Row label="Validation status" value={simulation.validation_status} />
          <Row
            label="Units"
            value="U [m/s], p kinematic [m²/s²], length [m], Vg inlet [m/s]"
          />
          <Row
            label="Boundary conditions"
            value="inlet fixed U; outlet p=0; rod/duct noSlip; wedge front/back"
          />
          <Row
            label="Fluid properties"
            value="ν = 1.5×10⁻⁵ m²/s (air ~300 K isothermal hypothesis)"
          />
        </tbody>
      </table>
      <p className="cfd-verify-footnote">
        Status <code>numerically_checked</code> requires an explicit{" "}
        <code>SIMPLE solution converged</code> announcement. Finishing at endTime without that
        message is <code>max_iterations_reached</code>, not convergence. Mesh independence remains
        separate from residual convergence.
      </p>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value}</td>
    </tr>
  );
}
