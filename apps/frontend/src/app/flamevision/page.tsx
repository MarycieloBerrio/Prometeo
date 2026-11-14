import Link from "next/link";
import { Suspense } from "react";

import type { Trial } from "@prometeo/contracts";

import { ProcessedRunGallery } from "@/components/flamevision/ProcessedRunGallery";
import { SourceLine } from "@/components/trials/SourceLine";
import { ApiDown } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, Section } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/LoadingState";
import { mediaUrl } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";

export default function FlameVisionPage() {
  return (
    <div className="page">
      <PageHeader slug="flamevision" />
      <Section
        title="Luminous edge track"
        hint="Recorded frame positions · pixels · unvalidated"
      >
        <Suspense fallback={<p className="muted">Loading processed runs…</p>}>
          <ProcessedRunGallery />
        </Suspense>
      </Section>
      <Section title="Trial-linked source video" hint="Only media supplied by trial records">
        <Suspense fallback={<LoadingState label="Checking source-linked media" />}>
          <TrialMedia />
        </Suspense>
      </Section>
      <div className="vision-next"><span>The track is visual evidence, not a calibrated spread rate.</span><Link href="/assistant">Ask what the evidence supports <Icon name="arrowRight" size={15} /></Link></div>
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
        <p className="vision-availability">No verified trial-linked video is available from the current API. The processed track above is a separate, unvalidated artifact; it is not mapped to an unrelated trial. <Link href="/explorer">Browse trial records <Icon name="arrowRight" size={14} /></Link></p>
      ) : (
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
      )}
    </>
  );
}
