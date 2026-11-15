"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { CfdFieldSample } from "@/domain/cfd";

type FieldMode = "u_mag" | "p";

/**
 * Interactive rz-plane viewer for downsampled OpenFOAM cell samples.
 * Plots a scalar field only (|U| or p). Does not invent streamlines from |U|.
 * When ux/uy/uz are present they are available for probing, not for fabricated glyphs.
 */
export function CfdFieldViewer({
  sample,
  sharedVelocityScale,
}: {
  sample: CfdFieldSample;
  /** Optional fixed |U| color scale across cases (m/s). */
  sharedVelocityScale?: { min: number; max: number };
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mode, setMode] = useState<FieldMode>("u_mag");
  const [hover, setHover] = useState<{
    r: number;
    z: number;
    value: number;
    uz?: number;
  } | null>(null);
  const [zoom, setZoom] = useState(1);

  const extents = useMemo(() => {
    const rs = sample.points.map((p) => Math.hypot(p.x, p.y));
    const zs = sample.points.map((p) => p.z);
    const vals = sample.points.map((p) => (mode === "u_mag" ? p.u_mag : p.p));
    let v0 = Math.min(...vals);
    let v1 = Math.max(...vals);
    if (mode === "u_mag" && sharedVelocityScale) {
      v0 = sharedVelocityScale.min;
      v1 = sharedVelocityScale.max;
    }
    return {
      r0: Math.min(...rs),
      r1: Math.max(...rs),
      z0: Math.min(...zs),
      z1: Math.max(...zs),
      v0,
      v1,
    };
  }, [sample, mode, sharedVelocityScale]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "#0b0d10";
    ctx.fillRect(0, 0, w, h);

    const pad = 36;
    const legendW = 18;
    const { r0, r1, z0, z1, v0, v1 } = extents;
    const spanR = (r1 - r0) || 1;
    const spanZ = (z1 - z0) || 1;
    const spanV = (v1 - v0) || 1;
    const plotW = w - 2 * pad - 48;

    for (const p of sample.points) {
      const r = Math.hypot(p.x, p.y);
      const value = mode === "u_mag" ? p.u_mag : p.p;
      const px = pad + ((r - r0) / spanR) * plotW * zoom;
      const py = h - pad - ((p.z - z0) / spanZ) * (h - 2 * pad) * zoom;
      ctx.fillStyle = colorFor((value - v0) / spanV);
      ctx.fillRect(px - 2, py - 2, 4, 4);
    }

    // Numeric color legend
    const lx = w - pad - legendW;
    for (let i = 0; i < 100; i++) {
      const t = i / 99;
      ctx.fillStyle = colorFor(t);
      ctx.fillRect(lx, pad + (1 - t) * (h - 2 * pad), legendW, (h - 2 * pad) / 100 + 1);
    }
    ctx.strokeStyle = "rgba(232,220,200,0.45)";
    ctx.strokeRect(lx, pad, legendW, h - 2 * pad);
    ctx.fillStyle = "rgba(232,220,200,0.85)";
    ctx.font = "11px ui-monospace, monospace";
    const unit = mode === "u_mag" ? (sample.units.velocity ?? "m/s") : (sample.units.pressure ?? "m²/s²");
    ctx.fillText(v1.toExponential(2), lx - 4, pad + 10);
    ctx.textAlign = "right";
    ctx.fillText(v0.toExponential(2), lx - 4, h - pad);
    ctx.fillText(unit, lx - 4, pad + (h - 2 * pad) / 2);
    ctx.textAlign = "left";

    ctx.strokeStyle = "rgba(232,220,200,0.35)";
    ctx.strokeRect(pad, pad, plotW, h - 2 * pad);
    ctx.fillStyle = "rgba(232,220,200,0.75)";
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillText(`r → (${sample.units.length ?? "m"})`, pad, h - 12);
    ctx.save();
    ctx.translate(14, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("z axial →", 0, 0);
    ctx.restore();
  }, [sample, mode, extents, zoom]);

  return (
    <div className="cfd-viewer">
      <div className="cfd-viewer-toolbar">
        <label>
          Field
          <select value={mode} onChange={(e) => setMode(e.target.value as FieldMode)}>
            <option value="u_mag">|U| ({sample.units.velocity ?? "m/s"})</option>
            <option value="p">p ({sample.units.pressure ?? "m²/s²"})</option>
          </select>
        </label>
        <label>
          Zoom
          <input
            type="range"
            min={1}
            max={3}
            step={0.1}
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
        <button type="button" onClick={() => setZoom(1)}>
          Reset view
        </button>
      </div>
      <canvas
        ref={canvasRef}
        width={720}
        height={420}
        className="cfd-canvas"
        aria-label="CFD scalar field sample in r-z plane"
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const mx = event.clientX - rect.left;
          const my = event.clientY - rect.top;
          const pad = 36;
          const w = event.currentTarget.width;
          const h = event.currentTarget.height;
          const plotW = w - 2 * pad - 48;
          const { r0, r1, z0, z1 } = extents;
          const r = r0 + ((mx - pad) / (plotW * zoom || 1)) * (r1 - r0);
          const z = z0 + ((h - pad - my) / ((h - 2 * pad) * zoom || 1)) * (z1 - z0);
          let best = sample.points[0];
          let bestD = Number.POSITIVE_INFINITY;
          for (const p of sample.points) {
            const pr = Math.hypot(p.x, p.y);
            const d = (pr - r) ** 2 + (p.z - z) ** 2;
            if (d < bestD) {
              bestD = d;
              best = p;
            }
          }
          setHover({
            r: Math.hypot(best.x, best.y),
            z: best.z,
            value: mode === "u_mag" ? best.u_mag : best.p,
            uz: best.uz,
          });
        }}
      />
      <p className="cfd-viewer-meta">
        Scalar field from downsampled OpenFOAM cell centres · {sample.points.length} of{" "}
        {sample.n_points_source} cells (stride {sample.downsample_stride}). No streamlines —
        directions are not inferred from |U| alone.
        {sample.viewer_note ? ` ${sample.viewer_note}` : ""}
        {hover && (
          <>
            {" "}
            Probe: r={hover.r.toExponential(3)} m, z={hover.z.toExponential(3)} m, value=
            {hover.value.toExponential(3)}
            {hover.uz != null ? `, uz=${hover.uz.toExponential(3)} m/s` : ""}
          </>
        )}
      </p>
    </div>
  );
}

function colorFor(t: number): string {
  const x = Math.max(0, Math.min(1, t));
  const r = Math.round(20 + 200 * x);
  const g = Math.round(40 + 80 * (1 - Math.abs(x - 0.5) * 2));
  const b = Math.round(180 - 120 * x);
  return `rgb(${r},${g},${b})`;
}
