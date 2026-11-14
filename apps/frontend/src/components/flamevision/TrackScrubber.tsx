"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/ui/Icon";

export type TrackObservation = {
  frame: number;
  time_s: number;
  status: string;
  edge_px: number;
};

/** Inspect an offline track observation without implying spatial calibration. */
export function TrackScrubber({ observations }: { observations: TrackObservation[] }) {
  const [index, setIndex] = useState(0);
  const plot = useMemo(() => {
    if (observations.length === 0) return null;
    const width = 700;
    const height = 250;
    const pad = { left: 50, right: 18, top: 20, bottom: 34 };
    const times = observations.map((point) => point.time_s);
    const positions = observations.map((point) => point.edge_px);
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    const minEdge = Math.min(...positions);
    const maxEdge = Math.max(...positions);
    const x = (time: number) => pad.left + (time - minTime) / (maxTime - minTime || 1) * (width - pad.left - pad.right);
    const y = (edge: number) => height - pad.bottom - (edge - minEdge) / (maxEdge - minEdge || 1) * (height - pad.top - pad.bottom);
    const path = observations.map((point, pointIndex) => (pointIndex === 0 ? "M " : "L ") + x(point.time_s) + " " + y(point.edge_px)).join(" ");
    return { width, height, pad, minTime, maxTime, minEdge, maxEdge, x, y, path };
  }, [observations]);
  if (!plot || observations.length === 0) return <p className="small muted">No frame observations are available for inspection.</p>;

  const activeIndex = Math.min(index, observations.length - 1);
  const active = observations[activeIndex];
  const display = (value: number) => Number(value.toPrecision(5)).toString();

  return (
    <section className="track-scrubber" aria-label="Inspect recorded luminous-edge observations">
      <div className="track-heading"><div><span className="eyebrow">FRAME LOG / DIRECT INSPECTION</span><h3>Luminous edge position over time</h3></div><span className="small muted">{observations.length} recorded frames · pixel coordinates</span></div>
      <div className="track-workbench">
        <div className="track-plot">
        <svg viewBox={"0 0 " + plot.width + " " + plot.height} role="img" aria-label="Observed luminous edge position in pixels over time in seconds; use the frame selector below to inspect a point">
          <title>Recorded luminous edge position by time</title>
          {[plot.minEdge, plot.maxEdge].map((value) => (
            <g key={value}><line className="track-grid" x1={plot.pad.left} x2={plot.width - plot.pad.right} y1={plot.y(value)} y2={plot.y(value)} /><text className="track-tick" x={plot.pad.left - 8} y={plot.y(value)} textAnchor="end" dominantBaseline="middle">{display(value)}</text></g>
          ))}
          <path className="track-line" d={plot.path} />
          <line className="track-cursor" x1={plot.x(active.time_s)} x2={plot.x(active.time_s)} y1={plot.pad.top} y2={plot.height - plot.pad.bottom} />
          <circle className="track-marker" cx={plot.x(active.time_s)} cy={plot.y(active.edge_px)} r="6" />
          <text className="track-tick" x={plot.pad.left} y={plot.height - 8}>{display(plot.minTime)} s</text>
          <text className="track-tick" x={plot.width - plot.pad.right} y={plot.height - 8} textAnchor="end">{display(plot.maxTime)} s</text>
        </svg>
        </div>
        <aside className="track-reading" aria-live="polite">
          <span className="eyebrow">SELECTED FRAME</span>
          <strong className="track-frame">{active.frame}</strong>
          <dl>
            <div><dt>TIME</dt><dd>{display(active.time_s)} s</dd></div>
            <div><dt>EDGE POSITION</dt><dd>{display(active.edge_px)} px</dd></div>
            <div><dt>DETECTION</dt><dd>{active.status}</dd></div>
          </dl>
          <p className="small muted">Pixel position of the tracked luminous leading edge. It is not a calibrated spread-rate measurement or a reaction-front location.</p>
        </aside>
      </div>
      <div className="track-controls">
        <button className="btn" type="button" onClick={() => setIndex(Math.max(0, activeIndex - 1))} disabled={activeIndex === 0} aria-label="Previous recorded frame"><Icon name="arrowLeft" size={15} /></button>
        <label className="track-range"><span className="small">SCRUB RECORDED FRAMES</span><input type="range" min={0} max={observations.length - 1} value={activeIndex} onChange={(event) => setIndex(Number(event.target.value))} aria-label="Recorded frame" aria-valuetext={"Frame " + active.frame + ", " + display(active.time_s) + " seconds"} /></label>
        <button className="btn" type="button" onClick={() => setIndex(Math.min(observations.length - 1, activeIndex + 1))} disabled={activeIndex === observations.length - 1} aria-label="Next recorded frame"><Icon name="arrowRight" size={15} /></button>
        <span className="mono small">{activeIndex + 1} / {observations.length}</span>
      </div>
      <p className="track-footnote">Lines connect recorded frames for reading only. No intermediate values or calibrated spread rate are inferred.</p>
    </section>
  );
}
