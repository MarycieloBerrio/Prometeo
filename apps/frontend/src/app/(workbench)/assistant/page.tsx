import { Suspense } from "react";

import type { AskResponse } from "@prometeo/contracts";

import { AnswerPanel } from "@/components/assistant/AnswerPanel";
import { AskForm, type AskParams } from "@/components/assistant/AskForm";
import { ASK_WAIT_LABEL } from "@/components/assistant/labels";
import { ApiDown } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/LoadingState";
import { SearchKeyedSuspense } from "@/components/ui/SearchKeyedSuspense";
import { firstParam } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/assistant">["searchParams"];

export default function AssistantPage({ searchParams }: PageProps<"/assistant">) {
  // The form and the answer stream separately: the form is ready as soon as the URL is read,
  // while the answer can take up to a minute when a model writes the interpretation.
  return (
    <div className="page">
      <PageHeader slug="assistant" />
      <Suspense fallback={<LoadingState label="Preparing the question form" />}>
        <Question searchParams={searchParams} />
      </Suspense>
      <Suspense fallback={null}>
        <SearchKeyedSuspense when="q" fallback={<LoadingState label={ASK_WAIT_LABEL} />}>
          <Answer searchParams={searchParams} />
        </SearchKeyedSuspense>
      </Suspense>
    </div>
  );
}

async function readParams(searchParams: SearchParams): Promise<AskParams> {
  const raw = await searchParams;
  return {
    q: firstParam(raw.q)?.trim(),
    material: firstParam(raw.material),
    geometry: firstParam(raw.geometry),
    flow_direction: firstParam(raw.flow_direction),
    model: firstParam(raw.model),
  };
}

/** Models a question may pick. An engine that is down or has no model offers none. */
async function offeredModels() {
  try {
    return await gateway.assistantModels();
  } catch {
    return { default: null, models: [] };
  }
}

async function Question({ searchParams }: { searchParams: SearchParams }) {
  const [params, offered] = await Promise.all([readParams(searchParams), offeredModels()]);
  return <AskForm params={params} models={offered.models} defaultModel={offered.default} />;
}

async function Answer({ searchParams }: { searchParams: SearchParams }) {
  const params = await readParams(searchParams);
  if (!params.q) return null;

  let response: AskResponse | null = null;
  let error: string | null = null;
  let syntheticEvidence = false;
  try {
    // A model named in the URL is honoured only if the engine offers it.
    const offered = await offeredModels();
    const model = offered.models.some((m) => m.id === params.model) ? params.model : null;
    response = await gateway.ask({
      question: params.q,
      model: model ?? null,
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

  return (
    <>
      {syntheticEvidence && <DemoBanner />}
      {error && <ApiDown message={error} />}
      {response && <AnswerPanel response={response} />}
    </>
  );
}
