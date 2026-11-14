import type { Trial } from "@prometeo/contracts";

import { formatQuantity } from "@/domain/format";

const SERIES = ["B16", "B19"] as const;
type SeriesId = (typeof SERIES)[number];

type Point = {
  trialId: string;
  series: SeriesId;
  flow: number;
  flowUnit: string;
  spread: number;
  spreadUnit: string;
  oxygenLabel: string | null;
};

const SERIES_STYLE: Record<SeriesId, { stroke: string; label: string }> = {
  B16: { stroke: "var(--accent)", label: "B16 · 18.2% O₂" },
  B19: { stroke: "var(--info)", label: "B19 · 17.5% O₂" },
};

function measurement(trial: Trial, name: string) {
  return trial.results.find((item) => item.name === name);
}

/** Collect curated B16/B19 points that already carry both ventilation and flame-spread rate. */
export function observationalSpreadPoints(trials: Trial[]): Point[] {
  const points: Point[] = [];
  for (const trial of trials) {
    if (trial.sample_id !== "B16" && trial.sample_id !== "B19") continue;
    if (!trial.flow_speed) continue;
    const fsr = measurement(trial, "flame_spread_rate");
    if (!fsr) continue;
    points.push({
      trialId: trial.id,
      series: trial.sample_id,
      flow: trial.flow_speed.value,
      flowUnit: trial.flow_speed.unit,
      spread: fsr.value.value,
      spreadUnit: fsr.value.unit,
      oxygenLabel: formatQuantity(trial.oxygen),
    });
  }
  return points.sort((a, b) => a.flow - b.flow || a.series.localeCompare(b.series));
}

/**
 * Observed Vf vs Vg for BASS-II B16/B19 condition points.
 * Values come only from Trial records already loaded via the gateway — no fitted model,
 * no causal delta, no interpolation presented as measurement.
 */
export function ObservationalSpreadChart({
  trials,
  highlight = [],
}: {
  trials: Trial[];
  highlight?: string[];
}) {
  const points = observationalSpreadPoints(trials);
  if (points.length < 2) return null;

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
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Observed flame spread rate versus ventilation for BASS-II B16 and B19">
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
              <circle
                cx={xScale(p.flow)}
                cy={yScale(p.spread)}
                r={selected ? 7 : 5}
                fill={SERIES_STYLE[p.series].stroke}
                className={selected ? "obs-point obs-point-hl" : "obs-point"}
              >
                <title>
                  {p.trialId}: Vg={p.flow} {p.flowUnit}, Vf={p.spread} {p.spreadUnit}
                  {p.oxygenLabel ? `, O₂=${p.oxygenLabel}` : ""}
                </title>
              </circle>
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
