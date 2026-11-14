import Link from "next/link";
import { Suspense } from "react";

import type { Trial } from "@prometeo/contracts";

import { SourceLine } from "@/components/trials/SourceLine";
import { ApiDown, Callout, EmptyState } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, Section } from "@/components/ui/PageHeader";
import { Steps, type Step } from "@/components/ui/Steps";
import { mediaUrl } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

const METHOD: Step[] = [
  { icon: "video", title: "Source video", note: "trial-linked footage" },
  { icon: "flame", title: "Track the edge", note: "frame by frame" },
  { icon: "chart", title: "Position vs time", note: "derived spread rate" },
  { icon: "check", title: "Validate", note: "against a reference" },
];

export default function FlameVisionPage() {
  return (
    <div className="page">
      <PageHeader slug="flamevision" />
      <Steps steps={METHOD} />
      <Suspense fallback={<p className="muted">Checking trial media…</p>}>
        <TrialMedia />
      </Suspense>
      <Section title="What the track means">
        <div className="principles">
          <div className="principle">
            <Icon name="flame" size={20} />
            <div><strong>Luminous leading edge ≠ reaction front</strong><p className="muted small">A visible edge is not the hottest zone or the heat-release region.</p></div>
          </div>
          <div className="principle">
            <Icon name="sigma" size={20} />
            <div><strong>Derived only with calibration</strong><p className="muted small">A spread rate requires spatial and temporal calibration plus a documented method.</p></div>
          </div>
          <div className="principle">
            <Icon name="alert" size={20} />
            <div><strong>Validation must be explicit</strong><p className="muted small">A trial video alone does not establish a validated track or measurement.</p></div>
          </div>
        </div>
      </Section>
    </div>
  );
}

async function TrialMedia() {
  let trials: Trial[];
  try {
    trials = await gateway.listTrials();
  } catch (error) {
    return <ApiDown message={error instanceof Error ? error.message : "Unknown error"} />;
  }
  const videos = trials.flatMap((trial) => trial.media
    .filter((media) => media.kind === "video" && mediaUrl(media.uri))
    .map((media) => ({ trial, media, uri: mediaUrl(media.uri)! })));
  return (
    <>
      {trials.some((trial) => trial.is_synthetic) && <DemoBanner />}
      {videos.length === 0 ? (
        <EmptyState icon="video" title="No verified video available" action={<Link href="/explorer" className="btn"><Icon name="search" size={16} />Browse trials</Link>}>
          No trial currently provides a source-linked video URI. An overlay or validation result is not available from this API.
        </EmptyState>
      ) : (
        <Section title="Videos in trial records" hint="Source links supplied by the Evidence Engine">
          <div className="grid">
            {videos.map(({ trial, media, uri }) => (
              <article className="card media-card" key={`${trial.id}-${uri}`}>
                <strong><Link className="link" href={`/explorer/${encodeURIComponent(trial.id)}`}>{trial.id} · {trial.material}</Link></strong>
                {trial.is_synthetic && <strong className="small">Synthetic fixture — not NASA footage</strong>}
                <p className="small muted">Video listed for this trial. Processing and validation are not established by the media record.</p>
                <a className="btn" href={uri} target="_blank" rel="noreferrer">Open source video <Icon name="external" size={14} /></a>
                <SourceLine provenance={trial.provenance} />
                {(media.start_s !== null || media.end_s !== null) && <p className="small muted">Recorded segment: {media.start_s ?? "?"}–{media.end_s ?? "?"} s</p>}
              </article>
            ))}
          </div>
        </Section>
      )}
      <Callout tone="info" title="No overlay API in the current contract">
        Flame-front overlays and validation can be shown after their source-linked artifacts are integrated.
      </Callout>
    </>
  );
}
