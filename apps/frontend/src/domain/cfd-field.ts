/**
 * Pure geometry, scaling and probing for the CFD scalar-field viewer.
 *
 * No React, no DOM and no path aliases, so it runs under `node --test`. Nothing here creates
 * data: every tile carries exactly one exported OpenFOAM cell-centre sample, and probing returns
 * that sample's value — never an interpolation.
 */

export type FieldMode = "u_mag" | "p";
export type ScaleMode = "global" | "local";

export type FieldPoint = { x: number; y: number; z: number; u_mag: number; p: number; uz?: number };

/** Physical domain in millimetres: r from the rod surface to the duct wall, z along the rod. */
export type Domain = { rMin: number; rMax: number; zMin: number; zMax: number };
export type Window = Domain;

export type Tile = {
  /** Cell-centre position (mm). */
  r: number;
  z: number;
  /** Drawn extent (mm): half-way to the neighbouring exported samples, clipped to the domain. */
  r0: number;
  r1: number;
  z0: number;
  z1: number;
  point: FieldPoint;
};

export type FieldGrid = {
  tiles: Tile[];
  rCenters: number[];
  zCenters: number[];
  domain: Domain;
  /** True when the export holds fewer samples than the mesh has cells. */
  decimated: boolean;
  /** Samples exported vs cells in the source mesh. */
  exported: number;
  sourceCells: number;
};

export type Geometry = {
  rod_radius_m: number;
  duct_outer_radius_m: number;
  domain_length_m: number;
};

const M_TO_MM = 1000;

/** Radius (mm) of a wedge cell centre: the wedge spans a small angle around the x axis. */
export function radiusMm(p: Pick<FieldPoint, "x" | "y">): number {
  return Math.hypot(p.x, p.y) * M_TO_MM;
}

/** Sorted distinct values, merging those closer than `tol` (cell centres repeat per row/column). */
export function distinct(values: number[], tol: number): number[] {
  const sorted = [...values].sort((a, b) => a - b);
  const out: number[] = [];
  for (const v of sorted) {
    if (out.length === 0 || v - out[out.length - 1] > tol) out.push(v);
  }
  return out;
}

function nearestIndex(centers: number[], v: number): number {
  let best = 0;
  for (let i = 1; i < centers.length; i++) {
    if (Math.abs(centers[i] - v) < Math.abs(centers[best] - v)) best = i;
  }
  return best;
}

/** Edges half-way between neighbouring centres; the outer edges are the physical bounds. */
function edges(centers: number[], lo: number, hi: number): number[] {
  const e = [lo];
  for (let i = 0; i < centers.length - 1; i++) e.push((centers[i] + centers[i + 1]) / 2);
  e.push(hi);
  return e;
}

/**
 * Lay exported cell-centre samples out as contiguous tiles. With a decimated export (e.g. every
 * other radial cell) a tile spans the region nearest to its sample, so the map has no artificial
 * gaps; the caller must state that tiles are nearest-sample regions, not extra cells.
 */
export function buildFieldGrid(
  points: FieldPoint[],
  sourceCells: number,
  geometry?: Geometry | null,
): FieldGrid {
  const rs = points.map(radiusMm);
  const zs = points.map((p) => p.z * M_TO_MM);
  const rCenters = distinct(rs, 1e-3);
  const zCenters = distinct(zs, 1e-3);

  const halfStep = (c: number[], i: number, j: number) => (c.length > 1 ? Math.abs(c[j] - c[i]) / 2 : 0.5);
  const domain: Domain = geometry
    ? {
        rMin: geometry.rod_radius_m * M_TO_MM,
        rMax: geometry.duct_outer_radius_m * M_TO_MM,
        zMin: 0,
        zMax: geometry.domain_length_m * M_TO_MM,
      }
    : {
        rMin: rCenters[0] - halfStep(rCenters, 0, 1),
        rMax: rCenters[rCenters.length - 1] + halfStep(rCenters, rCenters.length - 2, rCenters.length - 1),
        zMin: zCenters[0] - halfStep(zCenters, 0, 1),
        zMax: zCenters[zCenters.length - 1] + halfStep(zCenters, zCenters.length - 2, zCenters.length - 1),
      };

  const rEdges = edges(rCenters, domain.rMin, domain.rMax);
  const zEdges = edges(zCenters, domain.zMin, domain.zMax);
  const tiles: Tile[] = points.map((point, k) => {
    const i = nearestIndex(rCenters, rs[k]);
    const j = nearestIndex(zCenters, zs[k]);
    return {
      r: rs[k],
      z: zs[k],
      r0: rEdges[i],
      r1: rEdges[i + 1],
      z0: zEdges[j],
      z1: zEdges[j + 1],
      point,
    };
  });
  return {
    tiles,
    rCenters,
    zCenters,
    domain,
    decimated: points.length < sourceCells,
    exported: points.length,
    sourceCells,
  };
}

export type Range = { min: number; max: number };

export function fieldValue(p: FieldPoint, mode: FieldMode): number {
  return mode === "u_mag" ? p.u_mag : p.p;
}

export function rangeOf(points: FieldPoint[], mode: FieldMode): Range | null {
  if (points.length === 0) return null;
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const p of points) {
    const v = fieldValue(p, mode);
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return { min, max };
}

/** One range per variable across every case: what "Global / shared" scale mode uses. */
export function globalRanges(samples: Array<{ points: FieldPoint[] }>): Record<FieldMode, Range | null> {
  const all = samples.flatMap((s) => s.points);
  return { u_mag: rangeOf(all, "u_mag"), p: rangeOf(all, "p") };
}

export function activeRange(
  points: FieldPoint[],
  mode: FieldMode,
  scale: ScaleMode,
  global: Record<FieldMode, Range | null>,
): Range | null {
  return scale === "global" ? (global[mode] ?? rangeOf(points, mode)) : rangeOf(points, mode);
}

/** Viridis anchors (perceptually uniform, colour-blind safe), linear between anchors. */
const VIRIDIS: Array<[number, number, number]> = [
  [68, 1, 84],
  [72, 40, 120],
  [62, 74, 137],
  [49, 104, 142],
  [38, 130, 142],
  [31, 158, 137],
  [53, 183, 121],
  [109, 205, 89],
  [180, 222, 44],
  [253, 231, 37],
];

export function colormap(t: number): string {
  const x = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0)) * (VIRIDIS.length - 1);
  const i = Math.min(VIRIDIS.length - 2, Math.floor(x));
  const f = x - i;
  const [r0, g0, b0] = VIRIDIS[i];
  const [r1, g1, b1] = VIRIDIS[i + 1];
  const mix = (a: number, b: number) => Math.round(a + (b - a) * f);
  return `rgb(${mix(r0, r1)},${mix(g0, g1)},${mix(b0, b1)})`;
}

export function normalise(v: number, range: Range): number {
  const span = range.max - range.min;
  return span > 0 ? (v - range.min) / span : 0.5;
}

/** Plot rectangle in logical canvas pixels. z runs left → right (flow direction), r upwards. */
export type PlotRect = { left: number; top: number; width: number; height: number };

/**
 * Plot height for a given width so that 1 mm of r is drawn `radialMagnification` times as long
 * as 1 mm of z. Magnification 1 is true geometric scale.
 */
export function plotHeightFor(width: number, domain: Domain, radialMagnification: number): number {
  const zSpan = domain.zMax - domain.zMin;
  const rSpan = domain.rMax - domain.rMin;
  return Math.round(width * (rSpan / zSpan) * radialMagnification);
}

export function toCanvas(r: number, z: number, win: Window, rect: PlotRect): { x: number; y: number } {
  return {
    x: rect.left + ((z - win.zMin) / (win.zMax - win.zMin)) * rect.width,
    y: rect.top + rect.height - ((r - win.rMin) / (win.rMax - win.rMin)) * rect.height,
  };
}

export function fromCanvas(x: number, y: number, win: Window, rect: PlotRect): { r: number; z: number } {
  return {
    z: win.zMin + ((x - rect.left) / rect.width) * (win.zMax - win.zMin),
    r: win.rMin + ((rect.top + rect.height - y) / rect.height) * (win.rMax - win.rMin),
  };
}

/**
 * Client (CSS pixel) position → logical canvas position. The canvas is drawn in logical units
 * (`logicalWidth` × `logicalHeight`) but displayed at the element's CSS size, so the event
 * offset must be rescaled — using the logical size directly misplaces the probe.
 */
export function clientToLogical(
  clientX: number,
  clientY: number,
  box: { left: number; top: number; width: number; height: number },
  logicalWidth: number,
  logicalHeight: number,
): { x: number; y: number } {
  return {
    x: (clientX - box.left) * (logicalWidth / box.width),
    y: (clientY - box.top) * (logicalHeight / box.height),
  };
}

export function insideRect(x: number, y: number, rect: PlotRect): boolean {
  return x >= rect.left && x <= rect.left + rect.width && y >= rect.top && y <= rect.top + rect.height;
}

/** The tile whose drawn extent contains (r, z), or null outside the exported region. */
export function tileAt(grid: FieldGrid, r: number, z: number): Tile | null {
  for (const t of grid.tiles) {
    if (r >= t.r0 && r <= t.r1 && z >= t.z0 && z <= t.z1) return t;
  }
  return null;
}

/** A probe remembers which case and field it was taken on; a stale probe is never shown. */
export type Probe = { simulationId: string; mode: FieldMode; r: number; z: number };

export function probeReading(
  probe: Probe | null,
  simulationId: string,
  mode: FieldMode,
  grid: FieldGrid,
): { tile: Tile; value: number } | null {
  if (!probe || probe.simulationId !== simulationId || probe.mode !== mode) return null;
  const tile = tileAt(grid, probe.r, probe.z);
  return tile ? { tile, value: fieldValue(tile.point, mode) } : null;
}

/**
 * Zoomed view of `domain` around `center`, `factor` ≥ 1, clamped so the window never leaves the
 * domain (panning limits). factor = 1 returns the whole domain.
 */
export function zoomWindow(domain: Domain, factor: number, center: { r: number; z: number }): Window {
  const f = Math.max(1, factor);
  if (f === 1) return { ...domain }; // exact bounds: no floating drift at the domain edges
  const zSpan = (domain.zMax - domain.zMin) / f;
  const rSpan = (domain.rMax - domain.rMin) / f;
  const clamp = (c: number, half: number, lo: number, hi: number) => Math.min(Math.max(c, lo + half), hi - half);
  const zc = clamp(center.z, zSpan / 2, domain.zMin, domain.zMax);
  const rc = clamp(center.r, rSpan / 2, domain.rMin, domain.rMax);
  return { zMin: zc - zSpan / 2, zMax: zc + zSpan / 2, rMin: rc - rSpan / 2, rMax: rc + rSpan / 2 };
}

export function windowCenter(win: Window): { r: number; z: number } {
  return { r: (win.rMin + win.rMax) / 2, z: (win.zMin + win.zMax) / 2 };
}

/** Round tick values ("nice numbers") spanning [min, max]. */
export function niceTicks(min: number, max: number, target = 6): number[] {
  const span = max - min;
  if (!(span > 0)) return [min];
  const raw = span / Math.max(1, target);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= target) ?? 10 * mag;
  const first = Math.ceil(min / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let v = first; v <= max + step * 1e-9; v += step) ticks.push(Number(v.toPrecision(10)));
  return ticks;
}

export function formatValue(v: number): string {
  if (v === 0) return "0";
  const a = Math.abs(v);
  return a >= 0.01 && a < 1000 ? Number(v.toPrecision(3)).toString() : v.toExponential(2);
}
