"use client";

import Link from "next/link";
import { useState } from "react";

import type { Trial } from "@prometeo/contracts";

import { observationalSpreadPoints, type SeriesId } from "@/domain/observational-spread";

const SERIES = ["B16", "B19"] as const;

const SERIES_STYLE: Record<SeriesId, { stroke: string; label: string }> = {
  B16: { stroke: "var(--accent)", label: "B16 · 18.2% O₂" },
  B19: { stroke: "var(--info)", label: "B19 · 17.5% O₂" },
};

/**
 * Observed Vf vs Vg for BASS-II B16/B19 condition points.
 * Values come only from Trial records already loaded via the gateway — no fitted model,
 * no causal delta, no interpolation presented as measurement.
 */
export function ObservationalSpreadChart({
  trials,
  highlight = [],
  activeTrialId,
  onSelectTrial,
}: {
  trials: Trial[];
  highlight?: string[];
  /** Controlled focus trial (synced with CFD Physics Lab when provided). */
  activeTrialId?: string;
  onSelectTrial?: (trialId: string) => void;
}) {
  const points = observationalSpreadPoints(trials);
  const [internalId, setInternalId] = useState(highlight[0] ?? points[0]?.trialId ?? "");
  const activeId = activeTrialId ?? internalId;
  const setActiveId = (trialId: string) => {
    onSelectTrial?.(trialId);
    if (activeTrialId === undefined) setInternalId(trialId);
  };
  if (points.length < 2) return null;
  const active = points.find((point) => point.trialId === activeId) ?? points[0];
  const activeTrial = trials.find((trial) => trial.id === active.trialId);

  const width = 640;
  const height = 320;
  const pad = { top: 24, right: 24, bottom: 44, left: 56 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const flows = points.map((p) => p.flow);
  const spreads = points.map((p) => p.spread);
  const minX = Math.min(...flows);
  const maxX = Math.max(...flows);
  const minY = Math.min(...spreads);
  const maxY = Math.max(...spreads);
  const xPad = (maxX - minX) * 0.08 || 0.5;
  const yPad = (maxY - minY) * 0.15 || 0.01;
  const x0 = minX - xPad;
  const x1 = maxX + xPad;
  const y0 = Math.max(0, minY - yPad);
  const y1 = maxY + yPad;

  const xScale = (v: number) => pad.left + ((v - x0) / (x1 - x0)) * innerW;
  const yScale = (v: number) => pad.top + innerH - ((v - y0) / (y1 - y0)) * innerH;

  const flowUnit = points[0]?.flowUnit ?? "cm/s";
  const spreadUnit = points[0]?.spreadUnit ?? "mm/s";
  const highlightSet = new Set(highlight);

  const xTicks = uniqueTicks([minX, (minX + maxX) / 2, maxX]);
  const yTicks = uniqueTicks([y0, (y0 + y1) / 2, y1]);

  return (
    <figure className="obs-chart">
      <div className="obs-workbench">
      <div className="obs-plot">
      <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Select an observed BASS-II condition point">
        <title>Observed flame spread vs ventilation (B16 / B19)</title>

        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line
              className="obs-grid"
              x1={pad.left}
              x2={width - pad.right}
              y1={yScale(tick)}
              y2={yScale(tick)}
            />
            <text className="obs-tick" x={pad.left - 8} y={yScale(tick)} textAnchor="end" dominantBaseline="middle">
              {formatTick(tick)}
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line
              className="obs-grid"
              y1={pad.top}
              y2={height - pad.bottom}
              x1={xScale(tick)}
              x2={xScale(tick)}
            />
            <text className="obs-tick" x={xScale(tick)} y={height - pad.bottom + 16} textAnchor="middle">
              {formatTick(tick)}
            </text>
          </g>
        ))}

        <text className="obs-axis-label" x={width / 2} y={height - 8} textAnchor="middle">
          Ventilation / flow speed ({flowUnit})
        </text>
        <text
          className="obs-axis-label"
          x={16}
          y={height / 2}
          textAnchor="middle"
          transform={`rotate(-90 16 ${height / 2})`}
        >
          Flame spread rate ({spreadUnit})
        </text>

        {SERIES.map((series) => {
          const seriesPoints = points.filter((p) => p.series === series);
          if (seriesPoints.length < 2) return null;
          const d = seriesPoints.map((p, i) => `${i === 0 ? "M" : "L"} ${xScale(p.flow)} ${yScale(p.spread)}`).join(" ");
          return (
            <path
              key={series}
              className="obs-series-line"
              d={d}
              stroke={SERIES_STYLE[series].stroke}
              fill="none"
            />
          );
        })}

        {points.map((p) => {
          const selected = highlightSet.has(p.trialId);
          return (
            <g key={p.trialId}>
              <g>
                <title>
                  {`${p.trialId}: Vg=${p.flow} ${p.flowUnit}, Vf=${p.spread} ${p.spreadUnit}${p.oxygenLabel ? `, O2=${p.oxygenLabel}` : ""}`}
                </title>
                <circle
                  cx={xScale(p.flow)}
                  cy={yScale(p.spread)}
                  r={active.trialId === p.trialId ? 9 : selected ? 7 : 6}
                  fill={SERIES_STYLE[p.series].stroke}
                  className={"obs-point" + (selected ? " obs-point-hl" : "") + (active.trialId === p.trialId ? " obs-point-active" : "")}
                  role="button"
                  tabIndex={0}
                  aria-label={`${p.trialId}: ventilation ${p.flow} ${p.flowUnit}, flame spread ${p.spread} ${p.spreadUnit}`}
                  aria-pressed={active.trialId === p.trialId}
                  onClick={() => setActiveId(p.trialId)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setActiveId(p.trialId);
                    }
                  }}
                />
              </g>
              {selected && (
                <text
                  className="obs-point-label"
                  x={xScale(p.flow)}
                  y={yScale(p.spread) - 12}
                  textAnchor="middle"
                >
                  {highlight[0] === p.trialId ? "A" : highlight[1] === p.trialId ? "B" : "•"}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      </div>
      <aside className="obs-inspector" aria-live="polite">
        <p className="eyebrow">SELECTED CONDITION POINT</p>
        <strong className="mono">{active.trialId}</strong>
        <span className="small muted">BASS-II / physical sample {active.series}</span>
        <dl>
          <div><dt>VENTILATION</dt><dd>{active.flow} {active.flowUnit}</dd></div>
          <div><dt>FLAME SPREAD</dt><dd>{active.spread} {active.spreadUnit}</dd></div>
          <div><dt>OXYGEN</dt><dd>{active.oxygenLabel ?? "Not recorded"}</dd></div>
        </dl>
        <p className="small muted">{activeTrial?.results.find((item) => item.name === "flame_spread_rate")?.quality ?? "Recorded"} result. This point is a condition on sample {active.series}, not an independent ignition.</p>
        <div className="obs-inspector-actions">
          <Link href={"/explorer/" + encodeURIComponent(active.trialId)} className="btn btn-small">Inspect source</Link>
          <Link href={"/compare?a=" + encodeURIComponent(active.trialId)} className="btn btn-small">Use as trial A</Link>
        </div>
      </aside>
      </div>

      <figcaption className="legend">
        {SERIES.map((series) =>
          points.some((p) => p.series === series) ? (
            <span key={series}>
              <i className="swatch" style={{ background: SERIES_STYLE[series].stroke }} />
              {SERIES_STYLE[series].label}
            </span>
          ) : null,
        )}
        {highlight.length > 0 && (
          <span>
            <i className="swatch swatch-hl" /> Selected comparison trials
          </span>
        )}
      </figcaption>
      <p className="muted small">
        Observed condition points from curated BASS-II records (Link et al., Table S1). Lines connect
        measurements in the same sample series for readability only — they are not a fitted model and
        do not replace the Physics Validator verdict or withheld causal deltas.
      </p>
    </figure>
  );
}

function uniqueTicks(values: number[]): number[] {
  return [...new Set(values.map((v) => Number(v.toPrecision(4))))].sort((a, b) => a - b);
}

function formatTick(value: number): string {
  return Number(value.toPrecision(4)).toString();
}
