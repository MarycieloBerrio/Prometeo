import { Suspense } from "react";

import type { CompareRequest, CompareResponse, CoverageResponse, Trial } from "@prometeo/contracts";

import { CompareForm } from "@/components/compare/CompareForm";
import { ComparisonResult } from "@/components/compare/ComparisonResult";
import { CoverageMap } from "@/components/compare/CoverageMap";
import { ObservationalSpreadChart } from "@/components/compare/ObservationalSpreadChart";
import { ApiDown, Callout, EmptyState } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { PageHeader, Section } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/LoadingState";
import { allParams, firstParam, VARIABLES } from "@/domain/format";
import { observationalSpreadPoints } from "@/domain/observational-spread";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/compare">["searchParams"];
type Varied = CompareRequest["varied"];

export default function ComparePage({ searchParams }: PageProps<"/compare">) {
  return (
    <div className="page">
      <PageHeader slug="compare" />
      <Suspense fallback={<LoadingState label="Aligning experiment conditions" />}>
        <CompareLab searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function CompareLab({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const a = firstParam(params.a);
  const b = firstParam(params.b);
  const requestedMetric = firstParam(params.metric);
  const known = VARIABLES.map((v) => v.key);
  const requested = allParams(params.varied).filter((v) => known.includes(v));
  // Default matches the demo question: same fuel and geometry, two flow speeds.
  const varied = (requested.length > 0 ? requested : firstParam(params.submitted) === "1" ? [] : ["flow_speed"]) as Varied;

  let trials: Trial[] = [];
  let trialsError: string | null = null;
  try {
    trials = await gateway.listTrials();
  } catch (e) {
    trialsError = e instanceof Error ? e.message : "Unknown error";
  }

  const availableMetrics = new Set(trials.flatMap((trial) => trial.results.map((result) => result.name)));
  const metric = requestedMetric && availableMetrics.has(requestedMetric) ? requestedMetric : "flame_spread_rate";
  const invalidSelection = Boolean((a && !trials.some((trial) => trial.id === a)) || (b && !trials.some((trial) => trial.id === b)));

  let result: CompareResponse | null = null;
  let compareError: string | null = null;
  if (a && b && a !== b && !invalidSelection) {
    try {
      result = await gateway.compare({ trial_a: a, trial_b: b, varied, metrics: [metric] });
    } catch (e) {
      compareError = e instanceof Error ? e.message : "Unknown error";
    }
  }

  // Scope the coverage map to trial A's fuel and setup when a comparison is shown.
  const scope = result?.trials[0];
  let coverage: CoverageResponse | null = null;
  let coverageError: string | null = null;
  try {
    coverage = await gateway.coverage(
      scope
        ? {
            material: scope.material,
            geometry: scope.geometry,
            flow_direction: scope.flow_direction === "unknown" ? undefined : scope.flow_direction,
          }
        : {},
    );
  } catch (e) {
    coverageError = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <>
      {trialsError && <ApiDown message={trialsError} />}
      {trials.some((trial) => trial.is_synthetic) && <DemoBanner />}
      {!trialsError && trials.length === 0 && (
        <EmptyState icon="search" title="No recorded evidence">
          No trials are loaded. An empty dataset does not indicate that a material is safe.
        </EmptyState>
      )}
      {!trialsError && trials.length > 0 && <CompareForm key={[a, b, metric, ...varied].join("|")} trials={trials} a={a} b={b} varied={varied} metric={metric} />}
      {trials.length === 1 && (
        <Callout tone="neutral" title="Comparison unavailable">
          At least two distinct trials are needed. You can still inspect this trial and the evidence coverage.
        </Callout>
      )}
      {invalidSelection && <Callout tone="warn" title="Trial selection unavailable">Select trials currently in the Explorer.</Callout>}

      {a && b && a === b && (
        <Callout tone="warn" title="Pick two different trials">
          A and B are the same trial.
        </Callout>
      )}
      {compareError && <Callout tone="danger" title="Comparison failed">{compareError}</Callout>}

      {result && <ComparisonResult result={result} metric={metric} />}

      {observationalSpreadPoints(trials).length >= 2 && (
        <Section
          title="Observed flame spread vs ventilation"
          hint="BASS-II B16 / B19 condition points · measured values only"
        >
          <ObservationalSpreadChart
            trials={trials}
            highlight={result ? result.trials.map((t) => t.id) : [a, b].filter((id): id is string => Boolean(id))}
          />
        </Section>
      )}

      {coverageError && <Callout tone="warn" title="Coverage unavailable">{coverageError}</Callout>}
      {coverage && (
        <Section
          title="Evidence coverage"
          hint={scope ? `${scope.material} · ${scope.geometry}` : "All trials"}
        >
          <CoverageMap coverage={coverage} highlight={result ? result.trials.map((t) => t.id) : []} />
        </Section>
      )}
    </>
  );
}
