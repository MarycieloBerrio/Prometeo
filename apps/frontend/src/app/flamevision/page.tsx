import Link from "next/link";
import { Suspense } from "react";

import type { Trial } from "@prometeo/contracts";

import { SourceLine } from "@/components/trials/SourceLine";
import { ApiDown, Callout, EmptyState } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, Section } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/LoadingState";
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
      <div className="vision-method"><span className="eyebrow">IMAGE ANALYSIS / VALIDATION PATH</span><Steps steps={METHOD} /></div>
      <Suspense fallback={<LoadingState label="Checking source-linked media" />}>
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
        <div className="vision-workbench">
          <div className="vision-viewport">
            <div className="vision-viewport-heading"><span>FLAMEVISION / SOURCE VIEWER</span><span>NO SIGNAL</span></div>
            <div className="vision-reticle" aria-hidden="true"><Icon name="flame" size={54} /></div>
            <EmptyState icon="video" title="No verified flame video available yet" action={<Link href="/explorer" className="btn"><Icon name="search" size={16} />Browse experiments</Link>}>
              No trial currently provides a source-linked video URI. An overlay or validation result is not available from this API.
            </EmptyState>
            <div className="vision-viewport-footer"><span>AWAITING SOURCE MEDIA</span><span>NO TRACK GENERATED</span></div>
          </div>
          <aside className="vision-inspector" aria-label="Vision interpretation status">
            <p className="eyebrow">INTERPRETATION PANEL</p>
            <div><span>INPUT</span><strong>No verified video</strong><p>Only media referenced by a trial record can appear here.</p></div>
            <div><span>FEATURE</span><strong>Luminous leading edge</strong><p>Not the reaction front, temperature maximum or heat-release zone.</p></div>
            <div><span>VALIDATION</span><strong>Not available</strong><p>No track or published-reference match is supplied by the current API.</p></div>
          </aside>
        </div>
      ) : (
        <Section title="Videos in trial records" hint="Source links supplied by the Evidence Engine">
          <div className="vision-video-list">
            {videos.map(({ trial, media, uri }) => (
              <article className="vision-workbench" key={`${trial.id}-${uri}`}>
                <div className="vision-viewport">
                  <div className="vision-viewport-heading"><span>FLAMEVISION / {trial.id}</span><span>TRIAL MEDIA</span></div>
                  {/\.(mp4|webm|ogg)(\?|$)/i.test(uri) ? (
                    <video controls preload="metadata" src={uri} aria-label={`Source video for trial ${trial.id}`}>
                      Your browser cannot play this video. <a href={uri}>Open the source file</a>.
                    </video>
                  ) : <div className="vision-open"><Icon name="video" size={40} /><p>Video format requires its source viewer.</p><a className="btn" href={uri} target="_blank" rel="noreferrer">Open video <Icon name="external" size={14} /></a></div>}
                  <div className="vision-viewport-footer"><span>MEDIA FROM TRIAL RECORD</span><span>TRACK NOT VALIDATED</span></div>
                </div>
                <aside className="vision-inspector">
                  <p className="eyebrow">SOURCE & INTERPRETATION</p>
                  <strong><Link className="link" href={`/explorer/${encodeURIComponent(trial.id)}`}>{trial.id} · {trial.material}</Link></strong>
                  {trial.is_synthetic && <strong className="small">Synthetic fixture — not NASA footage</strong>}
                  <p className="small muted">The media record does not establish a processed or validated flame-front track.</p>
                  <SourceLine provenance={trial.provenance} />
                  {(media.start_s !== null || media.end_s !== null) && <p className="small muted">Recorded segment: {media.start_s ?? "?"}–{media.end_s ?? "?"} s</p>}
                  <a className="btn" href={uri} target="_blank" rel="noreferrer">Open source media <Icon name="external" size={14} /></a>
                </aside>
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
