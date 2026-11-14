import type { Trial } from "@prometeo/contracts";

import { formatQuantity } from "@/domain/format";

export type SeriesId = "B16" | "B19";
export type ObservedPoint = {
  trialId: string;
  series: SeriesId;
  flow: number;
  flowUnit: string;
  spread: number;
  spreadUnit: string;
  oxygenLabel: string | null;
};

/** Select recorded B16/B19 condition points only; no fitted or inferred values. */
export function observationalSpreadPoints(trials: Trial[]): ObservedPoint[] {
  const points: ObservedPoint[] = [];
  for (const trial of trials) {
    if (trial.sample_id !== "B16" && trial.sample_id !== "B19") continue;
    if (!trial.flow_speed) continue;
    const result = trial.results.find((item) => item.name === "flame_spread_rate");
    if (!result) continue;
    points.push({
      trialId: trial.id,
      series: trial.sample_id,
      flow: trial.flow_speed.value,
      flowUnit: trial.flow_speed.unit,
      spread: result.value.value,
      spreadUnit: result.value.unit,
      oxygenLabel: formatQuantity(trial.oxygen),
    });
  }
  return points.sort((a, b) => a.flow - b.flow || a.series.localeCompare(b.series));
}
