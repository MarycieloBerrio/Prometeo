"use client";

import { useMemo, useState } from "react";

import type { Trial } from "@prometeo/contracts";

import { CfdFieldViewer } from "@/components/compare/CfdFieldViewer";
import { NumericalVerificationPanel } from "@/components/compare/NumericalVerificationPanel";
import type { CfdFieldSample, CfdInterpretation, CfdSimulation } from "@/domain/cfd";
import { formatQuantity } from "@/domain/format";

type Props = {
  simulations: CfdSimulation[];
  fields: Record<string, CfdFieldSample>;
  interpretations: Record<string, CfdInterpretation>;
  trials: Trial[];
  preferredTrialIds?: string[];
  selectedTrialId?: string;
  onSelectTrial?: (trialId: string) => void;
};

/**
 * CFD Physics Lab — discrete precomputed OpenFOAM cases linked to B16 trials.
 * Does not run the solver in the browser; case control selects exported results only.
 */
export function CfdPhysicsLab({
  simulations,
  fields,
  interpretations,
  trials,
  preferredTrialIds = [],
  selectedTrialId,
  onSelectTrial,
}: Props) {
  const ordered = useMemo(
    () => [...simulations].sort((a, b) => a.inlet_velocity_cm_s - b.inlet_velocity_cm_s),
    [simulations],
  );

  const initialId = useMemo(() => {
    const focus = selectedTrialId ?? preferredTrialIds[0];
    if (focus) {
      const match = ordered.find((s) => s.reference_trial_id === focus);
      if (match) return match.simulation_id;
    }
    for (const trialId of preferredTrialIds) {
      const match = ordered.find((s) => s.reference_trial_id === trialId);
      if (match) return match.simulation_id;
    }
    return ordered[0]?.simulation_id ?? "";
  }, [ordered, preferredTrialIds, selectedTrialId]);

  const [internalId, setInternalId] = useState(initialId);
  const selectedFromTrial = selectedTrialId
    ? ordered.find((s) => s.reference_trial_id === selectedTrialId)?.simulation_id
    : undefined;
  const selectedId = selectedFromTrial ?? internalId;
  const setSelectedId = (simulationId: string) => {
    const simMatch = ordered.find((s) => s.simulation_id === simulationId);
    if (simMatch) onSelectTrial?.(simMatch.reference_trial_id);
    if (selectedTrialId === undefined) setInternalId(simulationId);
  };

  const sim = ordered.find((s) => s.simulation_id === selectedId) ?? ordered[0] ?? null;
  const trial = sim ? trials.find((t) => t.id === sim.reference_trial_id) : undefined;
  const field = sim ? fields[sim.simulation_id] : undefined;
  const interpretation = sim ? interpretations[sim.simulation_id] : undefined;
  const vf = trial?.results.find((r) => r.name === "flame_spread_rate");
  const sharedVelocityScale = useMemo(() => {
    const vals = Object.values(fields).flatMap((f) => f.points.map((p) => p.u_mag));
    if (vals.length === 0) return undefined;
    return { min: Math.min(...vals), max: Math.max(...vals) };
  }, [fields]);

  if (ordered.length === 0) {
    return (
      <div className="cfd-lab cfd-lab-empty">
        <p className="cfd-status unavailable">
          CFD result not available — solver execution or validation pending
        </p>
        <p className="muted">
          Comparison Lab and experimental charts remain available. Numerical simulations are stored
          separately from curated NASA trials.
        </p>
      </div>
    );
  }

  return (
    <div className="cfd-lab">
      <header className="cfd-lab-header">
        <div>
          <p className="cfd-kicker">Physics Lab · numerical_simulation</p>
          <h3>Axial opposed-flow CFD (non-reactive)</h3>
          <p>
            OpenFOAM isothermal laminar annular flow linked to BASS-II B16 condition points. Selects
            only precomputed cases — not a live solver.
          </p>
        </div>
        <div className={`cfd-badge ${sim?.validation_status ?? "pending"}`}>
          CFD · {statusLabel(sim)}
        </div>
      </header>

      <div className="cfd-case-rail" role="tablist" aria-label="CFD cases">
        {ordered.map((caseSim) => (
          <button
            key={caseSim.simulation_id}
            type="button"
            role="tab"
            aria-selected={caseSim.simulation_id === sim?.simulation_id}
            className={caseSim.simulation_id === sim?.simulation_id ? "active" : undefined}
            onClick={() => setSelectedId(caseSim.simulation_id)}
          >
            <span>{caseSim.inlet_velocity_cm_s.toFixed(2)} cm/s</span>
            <small>{caseSim.reference_trial_id.replace("BASS-II-", "")}</small>
          </button>
        ))}
      </div>

      {sim && (
        <div className="cfd-lab-grid">
          <aside className="cfd-side">
            <h4>Experiment (NASA / curated)</h4>
            <dl className="cfd-dl">
              <div>
                <dt>Trial</dt>
                <dd>{sim.reference_trial_id}</dd>
              </div>
              <div>
                <dt>Vg (recorded)</dt>
                <dd>
                  {sim.inlet_velocity_cm_s} cm/s ({sim.inlet_velocity_m_s} m/s)
                </dd>
              </div>
              <div>
                <dt>Vf (measured)</dt>
                <dd>{vf ? formatQuantity(vf.value) : "not in loaded trials"}</dd>
              </div>
              <div>
                <dt>O₂ context</dt>
                <dd>
                  {sim.oxygen_context_percent != null
                    ? `${sim.oxygen_context_percent}% (scenario id only)`
                    : "unverified"}
                </dd>
              </div>
              <div>
                <dt>Result kinds</dt>
                <dd>
                  experimental_observation · {trial ? "loaded" : "missing"} /{" "}
                  {sim.result_kind}
                </dd>
              </div>
            </dl>

            <h4>Model assumptions</h4>
            <ul className="cfd-list">
              {sim.geometry_assumptions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </aside>

          <div className="cfd-main">
            {sim.convergence_status !== "converged" && (
              <p className="cfd-status unavailable">
                Convergence not confirmed — {sim.convergence_status.split("_").join(" ")}.
                {sim.convergence_evidence ? ` ${sim.convergence_evidence}` : ""}
                {field
                  ? " Field samples may still be shown for inspection, but must not be labelled converged."
                  : ""}
              </p>
            )}
            {field ? (
              <CfdFieldViewer sample={field} sharedVelocityScale={sharedVelocityScale} />
            ) : (
              <p className="cfd-status unavailable">
                CFD result not available — solver execution or validation pending
              </p>
            )}
            <NumericalVerificationPanel simulation={sim} />
          </div>
        </div>
      )}

      {interpretation && (
        <section className="cfd-interpretation" aria-label="Scientific interpretation">
          <h4>Scientific interpretation</h4>
          <p className="cfd-question">{interpretation.question}</p>
          <div className="cfd-interp-grid">
            <InterpBlock letter="A" title="What NASA measured" items={interpretation.nasa_measured} />
            <InterpBlock
              letter="B"
              title="What our simulation computed"
              items={interpretation.simulation_computed}
            />
            <InterpBlock
              letter="C"
              title="Mechanisms in the literature"
              items={interpretation.literature_mechanisms}
            />
            <InterpBlock
              letter="D"
              title="What we cannot conclude"
              items={interpretation.cannot_conclude}
            />
          </div>
          <p className="cfd-sources">
            Sources: {interpretation.sources.join(" · ")}
          </p>
        </section>
      )}

      {sim && sim.limitations.length > 0 && (
        <details className="cfd-limitations">
          <summary>Simulation limitations</summary>
          <ul>
            {sim.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function InterpBlock({
  letter,
  title,
  items,
}: {
  letter: string;
  title: string;
  items: string[];
}) {
  return (
    <div className="cfd-interp-block">
      <p className="cfd-interp-label">
        <span>{letter}</span> {title}
      </p>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function statusLabel(sim: CfdSimulation | null | undefined): string {
  if (!sim) return "not available";
  if (sim.convergence_status === "converged" && sim.validation_status === "numerically_checked") {
    return "converged · numerically checked";
  }
  if (sim.convergence_status === "max_iterations_reached") {
    return "max iterations · not converged";
  }
  if (sim.convergence_status === "solver_failed") return "solver failed";
  if (sim.validation_status === "solver_executed") return "solver executed · not converged";
  return "pending";
}
