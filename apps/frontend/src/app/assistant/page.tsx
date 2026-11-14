import { Suspense } from "react";

import type { AskResponse } from "@prometeo/contracts";

import { AnswerPanel } from "@/components/assistant/AnswerPanel";
import { AskForm, type AskParams } from "@/components/assistant/AskForm";
import { ApiDown } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/LoadingState";
import { firstParam } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/assistant">["searchParams"];

export default function AssistantPage({ searchParams }: PageProps<"/assistant">) {
  return (
    <div className="page">
      <PageHeader slug="assistant" />
      <Suspense fallback={<LoadingState label="Auditing the evidence packet" />}>
        <Assistant searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Assistant({ searchParams }: { searchParams: SearchParams }) {
  const raw = await searchParams;
  const params: AskParams = {
    q: firstParam(raw.q)?.trim(),
    material: firstParam(raw.material),
    geometry: firstParam(raw.geometry),
    flow_direction: firstParam(raw.flow_direction),
  };

  let response: AskResponse | null = null;
  let error: string | null = null;
  let syntheticEvidence = false;
  if (params.q) {
    try {
      response = await gateway.ask({
        question: params.q,
        material: params.material ?? null,
        geometry: params.geometry ?? null,
        flow_direction: params.flow_direction ?? null,
        metric: "flame_spread_rate",
      });
      if (response.assessments.length > 0) {
        const assessedIds = new Set(response.assessments.map((item) => item.trial_id));
        const trials = await gateway.listTrials();
        syntheticEvidence = trials.some((trial) => trial.is_synthetic && assessedIds.has(trial.id));
      }
    } catch (e) {
      if (!response) error = e instanceof Error ? e.message : "Unknown error";
    }
  }

  return (
    <>
      <AskForm params={params} />
      {syntheticEvidence && <DemoBanner />}
      {error && <ApiDown message={error} />}
      {response && <AnswerPanel response={response} />}
    </>
  );
}
