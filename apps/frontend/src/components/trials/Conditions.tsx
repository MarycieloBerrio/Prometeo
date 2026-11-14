import type { Trial } from "@prometeo/contracts";

import { formatQuantity, humanize } from "@/domain/format";

interface Condition {
  label: string;
  value: string | null;
  detail?: string;
}

function conditionsOf(trial: Trial): Condition[] {
  return [
    {
      label: "Oxygen",
      value: formatQuantity(trial.oxygen),
    },
    {
      label: "Airflow",
      value: formatQuantity(trial.flow_speed),
      detail: trial.flow_direction === "unknown" ? undefined : trial.flow_direction,
    },
    {
      label: "Geometry",
      value: humanize(trial.geometry),
      detail: trial.thermal_regime === "unknown" ? undefined : `thermally ${trial.thermal_regime}`,
    },
    {
      label: "Thickness",
      value: formatQuantity(trial.thickness),
    },
    {
      label: "Pressure",
      value: formatQuantity(trial.pressure),
    },
  ];
}

/** Full conditions in a compact register for the trial sheet. */
export function ConditionTiles({ trial }: { trial: Trial }) {
  return (
    <dl className="condition-register">
      {conditionsOf(trial).map((c) => (
        <div key={c.label}>
          <dt>{c.label}</dt>
          <dd className={c.value ? undefined : "muted"}>{c.value ?? "Not recorded"}</dd>
          {c.detail && <dd className="condition-detail">{c.detail}</dd>}
        </div>
      ))}
    </dl>
  );
}
