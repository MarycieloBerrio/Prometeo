"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";

import {
  activeRange,
  buildFieldGrid,
  clientToLogical,
  colormap,
  formatValue,
  fromCanvas,
  insideRect,
  niceTicks,
  normalise,
  plotHeightFor,
  probeReading,
  toCanvas,
  windowCenter,
  zoomWindow,
  type FieldMode,
  type PlotRect,
  type Probe,
  type Range,
  type ScaleMode,
} from "@/domain/cfd-field";
import type { CfdFieldSample, CfdGeometry } from "@/domain/cfd";

const LOGICAL_WIDTH = 780;
const MARGIN = { left: 72, right: 150, top: 44, bottom: 54 };
const PLOT_WIDTH = LOGICAL_WIDTH - MARGIN.left - MARGIN.right;
const MAGNIFICATIONS = [1, 2, 3] as const;

const FIELD_LABEL: Record<FieldMode, string> = {
  u_mag: "|U| velocity magnitude",
  p: "p kinematic pressure (p/ρ, relative)",
};

function unitOf(sample: CfdFieldSample, mode: FieldMode): string {
  return mode === "u_mag" ? (sample.units.velocity ?? "m/s") : "m²/s²";
}

/**
 * Scalar-field viewer for exported OpenFOAM cell-centre samples in the r–z plane.
 *
 * - Plots one scalar (|U| or kinematic p) as contiguous tiles; never streamlines (vectors are
 *   not reconstructed from |U|).
 * - A decimated export is shown as nearest-sample tiles and declared as such; no interpolation.
 * - A probe belongs to the case and field it was taken on, so switching either never shows a
 *   reading from another simulation.
 */
export function CfdFieldViewer({
  sample,
  geometry,
  globalRanges,
}: {
  sample: CfdFieldSample;
  geometry?: CfdGeometry | null;
  /** Shared colour ranges across every loaded case, per variable (Global scale mode). */
  globalRanges: Record<FieldMode, Range | null>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mode, setMode] = useState<FieldMode>("u_mag");
  const [scale, setScale] = useState<ScaleMode>("local");
  const [magnification, setMagnification] = useState<number>(2);
  const [zoom, setZoom] = useState(1);
  const [center, setCenter] = useState<{ r: number; z: number } | null>(null);
  const [probe, setProbe] = useState<Probe | null>(null);
  const drag = useRef<{ x: number; y: number; center: { r: number; z: number } } | null>(null);

  const grid = useMemo(
    () => buildFieldGrid(sample.points, sample.n_points_source, geometry),
    [sample, geometry],
  );
  const plotHeight = plotHeightFor(PLOT_WIDTH, grid.domain, magnification);
  const logicalHeight = plotHeight + MARGIN.top + MARGIN.bottom;
  const rect: PlotRect = { left: MARGIN.left, top: MARGIN.top, width: PLOT_WIDTH, height: plotHeight };
  const win = zoomWindow(grid.domain, zoom, center ?? windowCenter(grid.domain));
  const range = activeRange(sample.points, mode, scale, globalRanges);
  const unit = unitOf(sample, mode);
  const reading = probeReading(probe, sample.simulation_id, mode, grid);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(LOGICAL_WIDTH * dpr);
    canvas.height = Math.round(logicalHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawField(ctx, { grid, rect, win, mode, range, unit, scale, logicalHeight, probeTile: reading?.tile ?? null });
  }, [grid, rect.height, win.zMin, win.zMax, win.rMin, win.rMax, mode, range, unit, scale, logicalHeight, reading]); // eslint-disable-line react-hooks/exhaustive-deps

  const toLogical = (event: PointerEvent<HTMLCanvasElement>) =>
    clientToLogical(
      event.clientX,
      event.clientY,
      event.currentTarget.getBoundingClientRect(),
      LOGICAL_WIDTH,
      logicalHeight,
    );

  const onPointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
    const { x, y } = toLogical(event);
    if (zoom > 1 && insideRect(x, y, rect)) {
      drag.current = { x, y, center: windowCenter(win) };
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const onPointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
    const { x, y } = toLogical(event);
    if (drag.current) {
      const start = drag.current;
      const dz = ((x - start.x) / rect.width) * (win.zMax - win.zMin);
      const dr = ((y - start.y) / rect.height) * (win.rMax - win.rMin);
      // Clamp through zoomWindow so panning can never leave the physical domain.
      setCenter(windowCenter(zoomWindow(grid.domain, zoom, { z: start.center.z - dz, r: start.center.r + dr })));
      return;
    }
    if (!insideRect(x, y, rect)) return;
    const { r, z } = fromCanvas(x, y, win, rect);
    setProbe({ simulationId: sample.simulation_id, mode, r, z });
  };

  const endDrag = () => {
    drag.current = null;
  };

  const resetView = () => {
    setZoom(1);
    setCenter(null);
  };

  const stride = sample.downsample_stride;
  return (
    <div className="cfd-viewer">
      <div className="cfd-viewer-toolbar">
        <label>
          Field
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as FieldMode);
              setProbe(null);
            }}
          >
            <option value="u_mag">|U| (m/s)</option>
            <option value="p">p kinematic (m²/s²)</option>
          </select>
        </label>
        <label>
          Colour scale
          <select value={scale} onChange={(e) => setScale(e.target.value as ScaleMode)}>
            <option value="local">Local — this case</option>
            <option value="global">Global — shared by all cases</option>
          </select>
        </label>
        <label>
          Radial axis
          <select value={magnification} onChange={(e) => setMagnification(Number(e.target.value))}>
            {MAGNIFICATIONS.map((m) => (
              <option key={m} value={m}>
                {m === 1 ? "×1 (true scale)" : `×${m} magnified`}
              </option>
            ))}
          </select>
        </label>
        <label>
          Zoom ×{zoom.toFixed(1)}
          <input
            type="range"
            min={1}
            max={4}
            step={0.1}
            value={zoom}
            aria-label="Zoom factor"
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
        <button type="button" onClick={resetView}>
          Reset view
        </button>
      </div>

      <canvas
        ref={canvasRef}
        className="cfd-canvas"
        style={{ aspectRatio: `${LOGICAL_WIDTH} / ${logicalHeight}`, cursor: zoom > 1 ? "grab" : "crosshair" }}
        aria-label={`CFD ${FIELD_LABEL[mode]} in the r–z plane, ${sample.simulation_id}`}
        data-simulation-id={sample.simulation_id}
        data-field={mode}
        data-scale={scale}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      />

      <p className="cfd-viewer-probe" aria-live="polite" data-testid="cfd-probe">
        {reading ? (
          <>
            Probe · {sample.simulation_id} · r = {reading.tile.r.toFixed(2)} mm, z ={" "}
            {reading.tile.z.toFixed(2)} mm → {mode === "u_mag" ? "|U|" : "p"} ={" "}
            {reading.value.toExponential(3)} {unit}
            {mode === "u_mag" && reading.tile.point.uz != null
              ? ` (uz = ${reading.tile.point.uz.toExponential(3)} m/s)`
              : ""}{" "}
            — exported cell-centre value, not interpolated.
          </>
        ) : (
          <>Probe: hover the field to read the nearest exported cell-centre value of this case.</>
        )}
      </p>

      <p className="cfd-viewer-meta">
        {magnification === 1
          ? "True geometric scale (×1): 1 mm radial = 1 mm axial on screen. "
          : `Radial axis visually magnified ×${magnification} for boundary-layer inspection — not a to-scale geometry. `}
        Domain: r = {grid.domain.rMin.toFixed(1)}–{grid.domain.rMax.toFixed(1)} mm (rod surface → circularised duct
        wall), z = {grid.domain.zMin.toFixed(0)}–{grid.domain.zMax.toFixed(0)} mm.{" "}
        {grid.decimated
          ? `Export holds ${grid.exported} of ${grid.sourceCells} mesh cells (${grid.rCenters.length} radial × ${grid.zCenters.length} axial samples, stride ${stride}); each tile shows the nearest exported sample — the skipped cells are not reconstructed or interpolated.`
          : `Full resolution: ${grid.exported} cells (${grid.rCenters.length} radial × ${grid.zCenters.length} axial); each tile is one OpenFOAM cell.`}{" "}
        Scalar map only: no streamlines are drawn from |U|.{" "}
        {mode === "p"
          ? "p is kinematic pressure relative to the outlet (p = 0 there), not the absolute BASS-II cabin pressure."
          : ""}
      </p>
    </div>
  );
}

function drawField(
  ctx: CanvasRenderingContext2D,
  o: {
    grid: ReturnType<typeof buildFieldGrid>;
    rect: PlotRect;
    win: ReturnType<typeof zoomWindow>;
    mode: FieldMode;
    range: Range | null;
    unit: string;
    scale: ScaleMode;
    logicalHeight: number;
    probeTile: ReturnType<typeof buildFieldGrid>["tiles"][number] | null;
  },
) {
  const { grid, rect, win, mode, range, unit, scale, logicalHeight, probeTile } = o;
  const ink = "rgba(232,220,200,0.88)";
  const faint = "rgba(232,220,200,0.35)";
  ctx.fillStyle = "#0b0d10";
  ctx.fillRect(0, 0, LOGICAL_WIDTH, logicalHeight);

  // ---- field tiles, clipped to the plot area so zoom never spills over axes or legend
  ctx.save();
  ctx.beginPath();
  ctx.rect(rect.left, rect.top, rect.width, rect.height);
  ctx.clip();
  if (range) {
    for (const t of grid.tiles) {
      if (t.z1 < win.zMin || t.z0 > win.zMax || t.r1 < win.rMin || t.r0 > win.rMax) continue;
      const a = toCanvas(t.r1, t.z0, win, rect);
      const b = toCanvas(t.r0, t.z1, win, rect);
      ctx.fillStyle = colormap(normalise(mode === "u_mag" ? t.point.u_mag : t.point.p, range));
      // +0.6 px overlap hides anti-aliasing seams between contiguous tiles.
      ctx.fillRect(a.x, a.y, b.x - a.x + 0.6, b.y - a.y + 0.6);
    }
  }
  if (probeTile) {
    const c = toCanvas(probeTile.r, probeTile.z, win, rect);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#000";
    ctx.beginPath();
    ctx.arc(c.x, c.y, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(c.x, c.y, 7, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();

  ctx.strokeStyle = faint;
  ctx.lineWidth = 1;
  ctx.strokeRect(rect.left, rect.top, rect.width, rect.height);

  // ---- physical boundaries (only where visible in the current window)
  ctx.font = "11px ui-monospace, monospace";
  ctx.textBaseline = "alphabetic";
  if (win.rMin <= grid.domain.rMin + 1e-9) {
    ctx.fillStyle = "#8a8f98";
    ctx.fillRect(rect.left, rect.top + rect.height + 1, rect.width, 4);
  }
  if (win.rMax >= grid.domain.rMax - 1e-9) {
    ctx.fillStyle = "#5c6168";
    ctx.fillRect(rect.left, rect.top - 5, rect.width, 4);
  }
  ctx.fillStyle = ink;
  ctx.textAlign = "left";
  ctx.fillText("inlet z = 0: uniform U = Vg  ·  flow →", rect.left, 16);
  ctx.textAlign = "right";
  ctx.fillText("outlet: p = 0", rect.left + rect.width, 16);
  ctx.textAlign = "left";
  ctx.fillStyle = faint;
  ctx.fillText("top edge: duct wall (no-slip) · bottom edge: PMMA rod surface (no-slip)", rect.left, 32);

  // ---- axes with numeric ticks (mm)
  ctx.fillStyle = ink;
  ctx.strokeStyle = faint;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const z of niceTicks(win.zMin, win.zMax, 6)) {
    const { x } = toCanvas(win.rMin, z, win, rect);
    ctx.beginPath();
    ctx.moveTo(x, rect.top + rect.height + 5);
    ctx.lineTo(x, rect.top + rect.height + 9);
    ctx.stroke();
    ctx.fillText(formatTick(z), x, rect.top + rect.height + 11);
  }
  ctx.fillText("z — axial position along the rod [mm]", rect.left + rect.width / 2, logicalHeight - 16);
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (const r of niceTicks(win.rMin, win.rMax, Math.max(3, Math.round(rect.height / 55)))) {
    const { y } = toCanvas(r, win.zMin, win, rect);
    ctx.beginPath();
    ctx.moveTo(rect.left - 5, y);
    ctx.lineTo(rect.left - 1, y);
    ctx.stroke();
    ctx.fillText(formatTick(r), rect.left - 8, y);
  }
  ctx.save();
  ctx.translate(16, rect.top + rect.height / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.fillText("r — radius [mm]", 0, 0);
  ctx.restore();

  // ---- legend: bar plus labels OUTSIDE the bar, variable, unit, min, max and scale mode
  if (range) {
    const barX = rect.left + rect.width + 26;
    const barW = 14;
    const barTop = rect.top;
    const barH = Math.max(rect.height, 60);
    for (let i = 0; i < 100; i++) {
      ctx.fillStyle = colormap(1 - i / 99);
      ctx.fillRect(barX, barTop + (i / 100) * barH, barW, barH / 100 + 1);
    }
    ctx.strokeStyle = faint;
    ctx.strokeRect(barX, barTop, barW, barH);
    const labelX = barX + barW + 8;
    ctx.fillStyle = ink;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(formatValue(range.max), labelX, barTop);
    ctx.textBaseline = "bottom";
    ctx.fillText(formatValue(range.min), labelX, barTop + barH);
    ctx.textBaseline = "middle";
    ctx.fillText(unit, labelX, barTop + barH / 2);
    ctx.textBaseline = "alphabetic";
    ctx.fillText(mode === "u_mag" ? "|U|" : "p (kinematic)", barX, barTop - 8);
    ctx.textBaseline = "top";
    ctx.fillStyle = faint;
    ctx.fillText(scale === "global" ? "global scale" : "local scale", barX - 4, barTop + barH + 8);
    ctx.fillText(scale === "global" ? "(all cases)" : "(this case)", barX - 4, barTop + barH + 21);
  }
}

function formatTick(v: number): string {
  return Number(v.toPrecision(4)).toString();
}
