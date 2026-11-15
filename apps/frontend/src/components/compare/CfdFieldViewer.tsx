"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { CfdFieldSample } from "@/domain/cfd";

type FieldMode = "u_mag" | "p";

/**
 * Interactive rz-plane viewer for downsampled OpenFOAM cell samples.
 * Coordinates: x≈radial, z≈axial (axisymmetric wedge export).
 */
export function CfdFieldViewer({ sample }: { sample: CfdFieldSample }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mode, setMode] = useState<FieldMode>("u_mag");
  const [hover, setHover] = useState<{ r: number; z: number; value: number } | null>(null);
  const [zoom, setZoom] = useState(1);

  const extents = useMemo(() => {
    const rs = sample.points.map((p) => Math.hypot(p.x, p.y));
    const zs = sample.points.map((p) => p.z);
    const vals = sample.points.map((p) => (mode === "u_mag" ? p.u_mag : p.p));
    return {
      r0: Math.min(...rs),
      r1: Math.max(...rs),
      z0: Math.min(...zs),
      z1: Math.max(...zs),
      v0: Math.min(...vals),
      v1: Math.max(...vals),
    };
  }, [sample, mode]);

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
    const { r0, r1, z0, z1, v0, v1 } = extents;
    const spanR = (r1 - r0) || 1;
    const spanZ = (z1 - z0) || 1;
    const spanV = (v1 - v0) || 1;

    for (const p of sample.points) {
      const r = Math.hypot(p.x, p.y);
      const value = mode === "u_mag" ? p.u_mag : p.p;
      const px = pad + ((r - r0) / spanR) * (w - 2 * pad) * zoom;
      const py = h - pad - ((p.z - z0) / spanZ) * (h - 2 * pad) * zoom;
      ctx.fillStyle = colorFor((value - v0) / spanV);
      ctx.fillRect(px - 2, py - 2, 4, 4);
    }

    ctx.strokeStyle = "rgba(232,220,200,0.35)";
    ctx.strokeRect(pad, pad, w - 2 * pad, h - 2 * pad);
    ctx.fillStyle = "rgba(232,220,200,0.75)";
    ctx.font = "12px ui-monospace, monospace";
    ctx.fillText(`r → (${sample.units.length ?? "m"})`, pad, h - 12);
    ctx.save();
    ctx.translate(14, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`z axial →`, 0, 0);
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
        aria-label="CFD field sample in r-z plane"
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const mx = event.clientX - rect.left;
          const my = event.clientY - rect.top;
          const pad = 36;
          const w = event.currentTarget.width;
          const h = event.currentTarget.height;
          const { r0, r1, z0, z1 } = extents;
          const r = r0 + ((mx - pad) / ((w - 2 * pad) * zoom || 1)) * (r1 - r0);
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
          });
        }}
      />
      <p className="cfd-viewer-meta">
        Downsampled OpenFOAM cell sample · {sample.points.length} of {sample.n_points_source} cells
        (stride {sample.downsample_stride}). Numerical simulation — not a NASA measurement.
        {hover && (
          <>
            {" "}
            Probe: r={hover.r.toExponential(3)} m, z={hover.z.toExponential(3)} m, value=
            {hover.value.toExponential(3)}
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
