import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import {
  activeRange,
  buildFieldGrid,
  clientToLogical,
  colormap,
  fromCanvas,
  globalRanges,
  niceTicks,
  plotHeightFor,
  probeReading,
  tileAt,
  toCanvas,
  zoomWindow,
  type FieldPoint,
  type PlotRect,
} from "./cfd-field.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const fieldsDir = path.join(here, "../../../../data/simulations/cfd/fields");
const GEOMETRY = { rod_radius_m: 0.0032, duct_outer_radius_m: 0.038, domain_length_m: 0.12 };

type Sample = {
  simulation_id: string;
  n_points_source: number;
  downsample_stride: number;
  points: FieldPoint[];
};
const load = (id: string): Sample =>
  JSON.parse(readFileSync(path.join(fieldsDir, `${id}.json`), "utf8")) as Sample;
const CASES = ["CFD-B16-Vg072", "CFD-B16-Vg083", "CFD-B16-Vg167", "CFD-B16-Vg755"].map(load);
const vg072 = CASES[0];
const vg755 = CASES[3];

describe("field grid from the real exported samples", () => {
  const grid = buildFieldGrid(vg072.points, vg072.n_points_source, GEOMETRY);

  it("uses only the samples actually exported and reports the decimation", () => {
    assert.equal(grid.exported, vg072.points.length);
    assert.equal(grid.sourceCells, vg072.n_points_source);
    assert.equal(grid.decimated, vg072.points.length < vg072.n_points_source);
    assert.equal(grid.tiles.length, vg072.points.length); // one tile per sample: nothing invented
    assert.equal(grid.rCenters.length * grid.zCenters.length, vg072.points.length);
  });

  it("spans the physical domain from the rod surface to the duct wall", () => {
    assert.deepEqual(grid.domain, { rMin: 3.2, rMax: 38, zMin: 0, zMax: 120 });
  });

  it("lays tiles out contiguously (no artificial gaps) in every axial row", () => {
    const rows = new Map<number, typeof grid.tiles>();
    for (const t of grid.tiles) rows.set(t.z, [...(rows.get(t.z) ?? []), t]);
    assert.equal(rows.size, grid.zCenters.length);
    for (const row of rows.values()) {
      row.sort((a, b) => a.r0 - b.r0);
      assert.equal(row[0].r0, 3.2);
      assert.equal(row[row.length - 1].r1, 38);
      for (let i = 1; i < row.length; i++) assert.ok(Math.abs(row[i].r0 - row[i - 1].r1) < 1e-9);
    }
  });

  it("every tile contains its own cell centre and probing it returns that sample", () => {
    for (const t of grid.tiles) {
      assert.ok(t.r >= t.r0 && t.r <= t.r1 && t.z >= t.z0 && t.z <= t.z1);
      assert.equal(tileAt(grid, t.r, t.z)?.point, t.point);
    }
  });

  it("flags a full-resolution export as not decimated", () => {
    const full = buildFieldGrid(vg072.points, vg072.points.length, GEOMETRY);
    assert.equal(full.decimated, false);
  });
});

describe("probe", () => {
  const grid = buildFieldGrid(vg072.points, vg072.n_points_source, GEOMETRY);
  const grid755 = buildFieldGrid(vg755.points, vg755.n_points_source, GEOMETRY);
  const rect: PlotRect = { left: 72, top: 44, width: 558, height: 324 };
  const win = grid.domain;

  it("maps CSS pixels to logical canvas pixels when the canvas is displayed scaled", () => {
    // Canvas drawn at 780 logical px but displayed at 776 CSS px (the reported mismatch).
    const box = { left: 100, top: 50, width: 776, height: 776 * (466 / 780) };
    const target = toCanvas(15.5, 54.75, win, rect);
    const clientX = box.left + target.x * (box.width / 780);
    const clientY = box.top + target.y * (box.height / 466);
    const logical = clientToLogical(clientX, clientY, box, 780, 466);
    assert.ok(Math.abs(logical.x - target.x) < 1e-9 && Math.abs(logical.y - target.y) < 1e-9);
    const { r, z } = fromCanvas(logical.x, logical.y, win, rect);
    assert.ok(Math.abs(r - 15.5) < 1e-9 && Math.abs(z - 54.75) < 1e-9);
    // Treating CSS pixels as logical pixels (the old behaviour) lands somewhere else.
    assert.ok(Math.abs(clientX - box.left - target.x) > 1);
  });

  it("reads the value of the cell under the probe, from the active case only", () => {
    const probe = { simulationId: vg072.simulation_id, mode: "u_mag" as const, r: 15.5, z: 54.75 };
    const reading = probeReading(probe, vg072.simulation_id, "u_mag", grid);
    assert.ok(reading);
    assert.equal(reading.value, reading.tile.point.u_mag);
    assert.ok(vg072.points.includes(reading.tile.point));
  });

  it("never shows a reading after switching case or field", () => {
    const probe = { simulationId: vg072.simulation_id, mode: "u_mag" as const, r: 15.5, z: 54.75 };
    assert.equal(probeReading(probe, vg755.simulation_id, "u_mag", grid755), null);
    assert.equal(probeReading(probe, vg072.simulation_id, "p", grid), null);
    assert.equal(probeReading(null, vg072.simulation_id, "u_mag", grid), null);
  });
});

describe("colour scales", () => {
  const global = globalRanges(CASES);

  it("global range spans every case for each variable", () => {
    const allU = CASES.flatMap((c) => c.points.map((p) => p.u_mag));
    const allP = CASES.flatMap((c) => c.points.map((p) => p.p));
    assert.deepEqual(global.u_mag, { min: Math.min(...allU), max: Math.max(...allU) });
    assert.deepEqual(global.p, { min: Math.min(...allP), max: Math.max(...allP) });
  });

  it("global mode uses the same limits in every case; local mode adapts to the case", () => {
    for (const mode of ["u_mag", "p"] as const) {
      const g072 = activeRange(vg072.points, mode, "global", global);
      const g755 = activeRange(vg755.points, mode, "global", global);
      assert.deepEqual(g072, g755);
      const l072 = activeRange(vg072.points, mode, "local", global);
      const l755 = activeRange(vg755.points, mode, "local", global);
      assert.notDeepEqual(l072, l755);
      assert.ok(l072 && g072 && l072.max <= g072.max);
    }
  });

  it("colormap is defined and clamped at the ends", () => {
    assert.equal(colormap(0), "rgb(68,1,84)");
    assert.equal(colormap(1), "rgb(253,231,37)");
    assert.equal(colormap(-3), colormap(0));
    assert.equal(colormap(7), colormap(1));
  });
});

describe("zoom and geometry", () => {
  const domain = { rMin: 3.2, rMax: 38, zMin: 0, zMax: 120 };

  it("zoom 1 shows the whole domain", () => {
    assert.deepEqual(zoomWindow(domain, 1, { r: 20, z: 60 }), domain);
  });

  it("zoomed windows never leave the domain, whatever the requested centre", () => {
    for (const factor of [1.5, 2, 4]) {
      for (const center of [
        { r: -50, z: -50 },
        { r: 1000, z: 1000 },
        { r: 3.2, z: 119 },
      ]) {
        const w = zoomWindow(domain, factor, center);
        assert.ok(w.rMin >= domain.rMin - 1e-9 && w.rMax <= domain.rMax + 1e-9);
        assert.ok(w.zMin >= domain.zMin - 1e-9 && w.zMax <= domain.zMax + 1e-9);
        assert.ok(Math.abs(w.zMax - w.zMin - 120 / factor) < 1e-9);
      }
    }
  });

  it("magnification 1 is true scale; ×k stretches only the radial axis", () => {
    assert.equal(plotHeightFor(558, domain, 1), Math.round(558 * (34.8 / 120)));
    assert.equal(plotHeightFor(558, domain, 3), Math.round(558 * (34.8 / 120) * 3));
  });

  it("nice ticks are round numbers inside the range", () => {
    assert.deepEqual(niceTicks(0, 120, 6), [0, 20, 40, 60, 80, 100, 120]);
    for (const t of niceTicks(3.2, 38, 5)) assert.ok(t >= 3.2 && t <= 38);
  });
});
