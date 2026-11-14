import Link from "next/link";
import { Suspense } from "react";

import type { CompareRequest, CompareResponse, CoverageResponse, Trial } from "@prometeo/contracts";

import { CompareForm } from "@/components/compare/CompareForm";
import { ComparisonResult } from "@/components/compare/ComparisonResult";
import { CoverageMap } from "@/components/compare/CoverageMap";
import { ApiDown, Callout, EmptyState } from "@/components/ui/Callout";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, Section } from "@/components/ui/PageHeader";
import { allParams, firstParam, VARIABLES } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/compare">["searchParams"];
type Varied = CompareRequest["varied"];

export default function ComparePage({ searchParams }: PageProps<"/compare">) {
  return (
    <div className="page">
      <PageHeader slug="compare" />
      <Suspense fallback={<p className="muted">Loading…</p>}>
        <CompareLab searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function CompareLab({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const a = firstParam(params.a);
  const b = firstParam(params.b);
  const known = VARIABLES.map((v) => v.key);
  const requested = allParams(params.varied).filter((v) => known.includes(v));
  // Default matches the demo question: same fuel and geometry, two flow speeds.
  const varied = (requested.length > 0 ? requested : ["flow_speed"]) as Varied;

  let trials: Trial[];
  try {
    trials = await gateway.listTrials();
  } catch (e) {
    return <ApiDown message={e instanceof Error ? e.message : "Unknown error"} />;
  }

  if (trials.length === 0) {
    return (
      <EmptyState icon="search" title="No trials loaded">
        The Evidence Engine has no trial records yet.
      </EmptyState>
    );
  }

  let result: CompareResponse | null = null;
  let compareError: string | null = null;
  if (a && b && a !== b) {
    try {
      result = await gateway.compare({ trial_a: a, trial_b: b, varied, metrics: ["flame_spread_rate"] });
    } catch (e) {
      compareError = e instanceof Error ? e.message : "Unknown error";
    }
  }

  // Scope the coverage map to trial A's fuel and setup when a comparison is shown.
  const scope = result?.trials[0];
  let coverage: CoverageResponse | null = null;
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
  } catch {
    coverage = null;
  }

  return (
    <>
      <CompareForm trials={trials} a={a} b={b} varied={varied} />

      {a && b && a === b && (
        <Callout tone="warn" title="Pick two different trials">
          A and B are the same trial.
        </Callout>
      )}
      {compareError && <Callout tone="danger" title="Comparison failed">{compareError}</Callout>}

      {result ? (
        <ComparisonResult result={result} />
      ) : (
        !compareError && (
          <EmptyState
            icon="compare"
            title="Pick trial A and trial B"
            action={
              <Link href="/explorer" className="btn">
                <Icon name="search" size={16} />
                Browse trials
              </Link>
            }
          >
            Prometeo first checks that the two trials can be compared. Only then it shows a difference.
          </EmptyState>
        )
      )}

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
