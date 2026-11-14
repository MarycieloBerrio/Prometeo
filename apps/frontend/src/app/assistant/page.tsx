import { Suspense } from "react";

import type { AskResponse } from "@prometeo/contracts";

import { AnswerPanel } from "@/components/assistant/AnswerPanel";
import { AskForm, type AskParams } from "@/components/assistant/AskForm";
import { ApiDown } from "@/components/ui/Callout";
import { PageHeader } from "@/components/ui/PageHeader";
import { Steps, type Step } from "@/components/ui/Steps";
import { firstParam } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/assistant">["searchParams"];

/** The fixed Evidence Engine pipeline. The model only writes the last step. */
const PIPELINE: Step[] = [
  { icon: "search", title: "Retrieve", note: "trials + documents" },
  { icon: "shield", title: "Validate", note: "physics match" },
  { icon: "sigma", title: "Compute", note: "no AI numbers" },
  { icon: "check", title: "Audit", note: "evidence tier" },
  { icon: "pen", title: "Explain", note: "or refuse" },
];

export default function AssistantPage({ searchParams }: PageProps<"/assistant">) {
  return (
    <div className="page">
      <PageHeader slug="assistant" />
      <Steps steps={PIPELINE} />
      <Suspense fallback={<p className="muted">Checking the evidence…</p>}>
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
  if (params.q) {
    try {
      response = await gateway.ask({
        question: params.q,
        material: params.material ?? null,
        geometry: params.geometry ?? null,
        flow_direction: params.flow_direction ?? null,
        metric: "flame_spread_rate",
      });
    } catch (e) {
      error = e instanceof Error ? e.message : "Unknown error";
    }
  }

  return (
    <>
      <AskForm params={params} />
      {error && <ApiDown message={error} />}
      {response && <AnswerPanel response={response} />}
    </>
  );
}
