import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { axisScale, deltaTSeconds, logTicks, paddedDomain } from "./spread-axis.ts";

describe("Δt from provenance", () => {
  it("reads the value stated in Table S1 provenance", () => {
    assert.equal(deltaTSeconds("Table S1; Δt = 170 s"), 170);
    assert.equal(deltaTSeconds("Table S1; Δt = 198 s"), 198);
  });
  it("returns null instead of guessing", () => {
    assert.equal(deltaTSeconds("Supplementary Table S1"), null);
    assert.equal(deltaTSeconds(null), null);
  });
});

describe("Vg axis", () => {
  it("log axis is monotonic and keeps the measured extremes labelled", () => {
    const [d0, d1] = paddedDomain("log", 0.72, 7.55);
    assert.ok(d0 > 0 && d0 < 0.72 && d1 > 7.55);
    const x = axisScale("log", d0, d1, 0, 100);
    assert.ok(x(0.72) < x(0.83) && x(0.83) < x(1.67) && x(1.67) < x(7.55));
    const ticks = logTicks(d0, d1, 0.72, 7.55);
    assert.ok(ticks.includes(0.72) && ticks.includes(7.55) && ticks.includes(1) && ticks.includes(5));
  });
  it("log spacing reflects ratios: 0.72→1.67 is wider than on a linear axis", () => {
    const lin = axisScale("linear", 0, 8, 0, 100);
    const log = axisScale("log", 0.5, 10, 0, 100);
    assert.ok(log(1.67) - log(0.72) > lin(1.67) - lin(0.72));
  });
  it("refuses a log axis that includes zero", () => {
    assert.throws(() => axisScale("log", 0, 1, 0, 1));
  });
});
