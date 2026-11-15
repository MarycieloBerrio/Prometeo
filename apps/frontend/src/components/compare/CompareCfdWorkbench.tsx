"use client";

import { useState } from "react";

import type { Trial } from "@prometeo/contracts";

import { CfdPhysicsLab } from "@/components/compare/CfdPhysicsLab";
import { ObservationalSpreadChart } from "@/components/compare/ObservationalSpreadChart";
import type { CfdFieldSample, CfdInterpretation, CfdSimulation } from "@/domain/cfd";
import { observationalSpreadPoints } from "@/domain/observational-spread";
import { Section } from "@/components/ui/PageHeader";
import { Callout } from "@/components/ui/Callout";

type Props = {
  trials: Trial[];
  highlightIds: string[];
  simulations: CfdSimulation[];
  fields: Record<string, CfdFieldSample>;
  interpretations: Record<string, CfdInterpretation>;
  cfdError: string | null;
};

/**
 * Shared focus trial between the observational Vg–Vf chart and the CFD Physics Lab.
 */
export function CompareCfdWorkbench({
  trials,
  highlightIds,
  simulations,
  fields,
  interpretations,
  cfdError,
}: Props) {
  const points = observationalSpreadPoints(trials);
  const b16Preferred =
    highlightIds.find((id) => id.startsWith("BASS-II-B16-")) ??
    points.find((p) => p.series === "B16")?.trialId ??
    highlightIds[0] ??
    "";
  const [focusTrialId, setFocusTrialId] = useState(b16Preferred);

  return (
    <>
      {points.length >= 2 && (
        <Section
          title="Observed flame spread vs ventilation"
          hint="BASS-II B16 / B19 condition points · measured values only"
        >
          <ObservationalSpreadChart
            trials={trials}
            highlight={highlightIds}
            activeTrialId={focusTrialId}
            onSelectTrial={setFocusTrialId}
          />
        </Section>
      )}

      <Section
        title="CFD Physics Lab"
        hint="numerical_simulation · linked to B16 · not a flame model"
      >
        {cfdError && (
          <Callout tone="warn" title="CFD API unavailable">
            {cfdError}. Experimental Comparison Lab above remains usable.
          </Callout>
        )}
        {!cfdError && (
          <CfdPhysicsLab
            simulations={simulations}
            fields={fields}
            interpretations={interpretations}
            trials={trials}
            preferredTrialIds={highlightIds}
            selectedTrialId={focusTrialId}
            onSelectTrial={setFocusTrialId}
          />
        )}
      </Section>
    </>
  );
}
