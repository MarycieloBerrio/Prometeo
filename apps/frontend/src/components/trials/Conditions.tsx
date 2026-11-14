import type { Trial } from "@prometeo/contracts";

import { Icon, type IconName } from "@/components/ui/Icon";
import { formatQuantity, humanize } from "@/domain/format";

interface Condition {
  icon: IconName;
  label: string;
  value: string | null;
  detail?: string;
}

function conditionsOf(trial: Trial): Condition[] {
  return [
    {
      icon: "oxygen",
      label: "Oxygen",
      value: formatQuantity(trial.oxygen),
    },
    {
      icon: "wind",
      label: "Airflow",
      value: formatQuantity(trial.flow_speed),
      detail: trial.flow_direction === "unknown" ? undefined : trial.flow_direction,
    },
    {
      icon: "box",
      label: "Geometry",
      value: humanize(trial.geometry),
      detail: trial.thermal_regime === "unknown" ? undefined : `thermally ${trial.thermal_regime}`,
    },
    {
      icon: "layers",
      label: "Thickness",
      value: formatQuantity(trial.thickness),
    },
    {
      icon: "gauge",
      label: "Pressure",
      value: formatQuantity(trial.pressure),
    },
  ];
}

/** Compact one-line conditions for cards. Unknown values are shown as "not recorded". */
export function ConditionChips({ trial }: { trial: Trial }) {
  return (
    <ul className="chips">
      {conditionsOf(trial)
        .slice(0, 3)
        .map((c) => (
          <li key={c.label} className={`chip${c.value ? "" : " chip-missing"}`} title={c.label}>
            <Icon name={c.icon} size={15} label={c.label} />
            <span>{c.value ?? "not recorded"}</span>
            {c.detail && <span className="muted">· {c.detail}</span>}
          </li>
        ))}
    </ul>
  );
}

/** Full conditions as icon tiles for the trial sheet. */
export function ConditionTiles({ trial }: { trial: Trial }) {
  return (
    <div className="tiles">
      {conditionsOf(trial).map((c) => (
        <div key={c.label} className="tile">
          <span className="tile-icon">
            <Icon name={c.icon} size={18} />
          </span>
          <span className="small muted">{c.label}</span>
          <strong className={c.value ? undefined : "muted"}>{c.value ?? "Not recorded"}</strong>
          {c.detail && <span className="small muted">{c.detail}</span>}
        </div>
      ))}
    </div>
  );
}
