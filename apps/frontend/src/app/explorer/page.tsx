import { Suspense } from "react";

import type { Trial } from "@prometeo/contracts";

import type { TrialQuery } from "@/application/ports/evidence-gateway";
import { TrialFilters } from "@/components/trials/TrialFilters";
import { TrialPicker } from "@/components/trials/TrialPicker";
import { ApiDown, EmptyState } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { firstParam } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/explorer">["searchParams"];

export default function ExplorerPage({ searchParams }: PageProps<"/explorer">) {
  // Static shell renders immediately; request-time data streams in under <Suspense>.
  return (
    <div className="page">
      <PageHeader slug="explorer" />
      <Suspense fallback={<p className="muted">Loading trials…</p>}>
        <TrialResults searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function TrialResults({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query: TrialQuery = {
    investigation: firstParam(params.investigation),
    material: firstParam(params.material),
    geometry: firstParam(params.geometry),
    flow_direction: firstParam(params.flow_direction),
    phenomenon: firstParam(params.phenomenon),
  };

  let trials: Trial[] = [];
  let error: string | null = null;
  try {
    trials = await gateway.listTrials(query);
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <>
      <TrialFilters query={query} />

      {error && <ApiDown message={error} />}

      {!error && trials.some((t) => t.is_synthetic) && (
        <DemoBanner />
      )}

      {!error && trials.length === 0 && (
        <EmptyState icon="search" title="No recorded evidence">
          No trial matches these filters. That is a gap in the data, not a sign that a material is safe.
        </EmptyState>
      )}

      {trials.length > 0 && (
        <>
          <p className="muted small">
            {trials.length} {trials.length === 1 ? "trial" : "trials"} · pick two to compare
          </p>
          <TrialPicker trials={trials} />
        </>
      )}
    </>
  );
}
