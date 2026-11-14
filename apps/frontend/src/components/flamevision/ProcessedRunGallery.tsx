import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ReactNode } from "react";

import { TrackScrubber, type TrackObservation } from "@/components/flamevision/TrackScrubber";
import { Callout } from "@/components/ui/Callout";
import { Icon } from "@/components/ui/Icon";

type IndexRun = {
  key: string;
  manifest: string;
  trial_key: string;
  prometeo_trial_id: string | null;
  validation_status: string;
  position_unit: string;
  rate_unit: string;
  credit: string;
};

type FlameVisionIndex = {
  schema: string;
  note: string;
  runs: IndexRun[];
};

type TrackSummary = {
  feature: string;
  feature_note: string;
  source: {
    url: string;
    license: string;
    trial_key: string;
    prometeo_trial_id: string | null;
    notes: string;
  };
  method: { name: string; start_s?: number; end_s?: number };
  diagnostics: {
    frames_analysed: number;
    detected: number;
    coverage: number;
    advance_px_per_s: number;
    fit: { slope_px_per_s: number; r_squared: number; samples: number };
  };
  verdict: string;
  validation: { status: string; reason: string; reference: null | string };
  observations: TrackObservation[];
};

const PUBLIC_ROOT = path.join(process.cwd(), "public", "experiments", "flamevision");

async function loadIndex(): Promise<FlameVisionIndex | null> {
  try {
    const raw = await readFile(path.join(PUBLIC_ROOT, "index.json"), "utf8");
    return JSON.parse(raw) as FlameVisionIndex;
  } catch {
    return null;
  }
}

async function loadTrack(runKey: string): Promise<TrackSummary | null> {
  try {
    const raw = await readFile(path.join(PUBLIC_ROOT, runKey, "track.json"), "utf8");
    return JSON.parse(raw) as TrackSummary;
  } catch {
    return null;
  }
}

/**
 * Gallery for processed FlameVision artifacts under public/experiments/flamevision.
 * These are static validation products (px units, UNVALIDATED until a reference exists).
 * They are not attached to Trial.media and must not invent a Prometeo trial link.
 */
export async function ProcessedRunGallery() {
  const index = await loadIndex();
  if (!index || index.runs.length === 0) {
    return (
      <Callout tone="neutral" title="No processed FlameVision runs">
        No static artifacts are published under /experiments/flamevision yet.
      </Callout>
    );
  }

  const runs = await Promise.all(
    index.runs.map(async (run) => ({
      run,
      track: await loadTrack(run.key),
    })),
  );

  return (
    <SectionBlock note={index.note}>
      {runs.map(({ run, track }) => {
        const base = `/experiments/flamevision/${run.key}`;
        const sample = track?.observations?.slice(0, 5) ?? [];
        return (
          <article className="fv-run" key={run.key}>
            <header className="fv-run-head">
              <div>
                <strong>{run.trial_key}</strong>
                <p className="small muted">{run.credit}</p>
              </div>
              <span className={`badge tone-${run.validation_status === "UNVALIDATED" ? "warn" : "ok"}`}>
                {run.validation_status}
              </span>
            </header>

            <p className="small">
              Tracked feature: luminous leading edge ({run.position_unit}). Rate unit: {run.rate_unit}.
              {run.prometeo_trial_id
                ? ` Linked trial: ${run.prometeo_trial_id}.`
                : " No Prometeo Trial.id is associated — do not map this run onto unrelated BASS-II sample IDs."}
            </p>

            {track && <TrackScrubber observations={track.observations} />}
            <details className="fv-keyframes">
              <summary>View source keyframes <Icon name="plus" size={16} /></summary>
              <figure className="fv-media">
                {/* Static processed artifact from Juanfer's validation pipeline */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`${base}/keyframes.jpg`} alt={`Keyframes for ${run.key}`} />
                <figcaption className="small muted">Keyframes of the luminous edge. This sequence is not a live overlay.</figcaption>
              </figure>
            </details>
            <details className="fv-exported-curve">
              <summary>View exported static curve</summary>
              <figure className="fv-media">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`${base}/curve.png`} alt={`Position vs time curve for ${run.key}`} />
                <figcaption className="small muted">Exported edge position vs time (px)</figcaption>
              </figure>
            </details>

            {track && (
              <div className="fv-stats">
                <div>
                  <span className="small muted">Pipeline verdict</span>
                  <strong>{track.verdict}</strong>
                </div>
                <div>
                  <span className="small muted">Advance (uncalibrated)</span>
                  <strong className="mono">
                    {Number(track.diagnostics.advance_px_per_s.toPrecision(4))} {run.rate_unit}
                  </strong>
                </div>
                <div>
                  <span className="small muted">Fit R²</span>
                  <strong className="mono">{Number(track.diagnostics.fit.r_squared.toPrecision(4))}</strong>
                </div>
                <div>
                  <span className="small muted">Frames detected</span>
                  <strong className="mono">
                    {track.diagnostics.detected}/{track.diagnostics.frames_analysed}
                  </strong>
                </div>
              </div>
            )}

            {track?.validation && (
              <Callout tone="warn" title={`Validation: ${track.validation.status}`}>
                {track.validation.reason}
              </Callout>
            )}

            {track?.feature_note && <p className="muted small">{track.feature_note}</p>}

            {sample.length > 0 && (
              <details className="fv-log">
                <summary>Inspect first five raw log rows</summary>
                <table>
                  <thead>
                    <tr>
                      <th>frame</th>
                      <th>time_s</th>
                      <th>status</th>
                      <th>edge_px</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sample.map((row) => (
                      <tr key={row.frame}>
                        <td className="mono">{row.frame}</td>
                        <td className="mono">{row.time_s}</td>
                        <td>{row.status}</td>
                        <td className="mono">{row.edge_px}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}

            <div className="fv-actions">
              <a className="btn" href={`${base}/track.csv`} download>
                Download track.csv <Icon name="external" size={14} />
              </a>
              <a className="btn" href={`${base}/track.json`} target="_blank" rel="noreferrer">
                Open track.json <Icon name="external" size={14} />
              </a>
              {track?.source.url && (
                <a className="btn" href={track.source.url} target="_blank" rel="noreferrer">
                  NASA PSI source <Icon name="external" size={14} />
                </a>
              )}
            </div>
            {track?.source.notes && <p className="muted small">{track.source.notes}</p>}
          </article>
        );
      })}
    </SectionBlock>
  );
}

function SectionBlock({ note, children }: { note: string; children: ReactNode }) {
  return (
    <section className="fv-gallery">
      <p className="muted small">{note}</p>
      <div className="stack">{children}</div>
    </section>
  );
}
