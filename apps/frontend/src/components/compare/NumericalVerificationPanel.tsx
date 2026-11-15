"use client";

import type { CfdSimulation } from "@/domain/cfd";

/** Shows only metrics present in the CFD manifest — never invents PASS. */
export function NumericalVerificationPanel({ simulation }: { simulation: CfdSimulation }) {
  const residualEntries = Object.entries(simulation.residuals);
  return (
    <section className="cfd-verify" aria-label="Numerical Verification">
      <h4>Numerical Verification</h4>
      <p className="muted">
        Distinguishes solver execution, numerical checks, and experimental model validation —
        these are not equivalent.
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
          <Row label="Mesh quality metrics" value="not verified (MVP)" />
          <Row
            label="Residuals (final)"
            value={
              residualEntries.length > 0
                ? residualEntries.map(([k, v]) => `${k}=${v.toExponential(3)}`).join(" · ")
                : "not verified"
            }
          />
          <Row label="Convergence" value={simulation.convergence_status} />
          <Row
            label="Mass / continuity balance"
            value={
              simulation.mass_balance_error != null
                ? `${simulation.mass_balance_error.toExponential(3)} (${simulation.mass_balance_status})`
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
        Mesh independence is <strong>not demonstrated</strong> for this MVP. Status{" "}
        <code>numerically_checked</code> means residuals/continuity were read from a real solver
        log — not that the model is experimentally validated.
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
