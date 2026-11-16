/**
 * Pure helpers for the observed Vf–Vg chart (no React, no path aliases: runs under node --test).
 */

export type AxisKind = "linear" | "log";

/**
 * Δt in seconds as recorded in the measurement provenance ("Table S1; Δt = 170 s").
 * Returns null when the provenance does not state it — never a guessed value.
 */
export function deltaTSeconds(text: string | null | undefined): number | null {
  if (!text) return null;
  const m = /Δt\s*=\s*(\d+(?:\.\d+)?)\s*s\b/.exec(text);
  return m ? Number(m[1]) : null;
}

/** Map a data value to [p0, p1] on a linear or base-10 log axis spanning [d0, d1]. */
export function axisScale(kind: AxisKind, d0: number, d1: number, p0: number, p1: number): (v: number) => number {
  if (kind === "log") {
    if (!(d0 > 0 && d1 > d0)) throw new Error("log axis needs 0 < d0 < d1");
    const l0 = Math.log10(d0);
    const l1 = Math.log10(d1);
    return (v) => p0 + ((Math.log10(v) - l0) / (l1 - l0)) * (p1 - p0);
  }
  return (v) => p0 + ((v - d0) / (d1 - d0)) * (p1 - p0);
}

/** Padded domain for the axis; on a log axis padding is multiplicative so it stays positive. */
export function paddedDomain(kind: AxisKind, min: number, max: number): [number, number] {
  if (kind === "log") {
    const f = max > min ? (max / min) ** 0.06 : 1.25;
    return [min / f, max * f];
  }
  const pad = (max - min) * 0.08 || 0.5;
  return [min - pad, max + pad];
}

/** 1-2-5 ticks per decade inside [d0, d1], plus the data extremes so measured Vg stay labelled. */
export function logTicks(d0: number, d1: number, dataMin: number, dataMax: number): number[] {
  const ticks = new Set<number>([dataMin, dataMax]);
  for (let e = Math.floor(Math.log10(d0)); e <= Math.ceil(Math.log10(d1)); e++) {
    for (const m of [1, 2, 5]) {
      const v = Number((m * 10 ** e).toPrecision(6));
      if (v >= d0 && v <= d1) ticks.add(v);
    }
  }
  return [...ticks].sort((a, b) => a - b);
}
