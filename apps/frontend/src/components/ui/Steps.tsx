import { Fragment } from "react";

import { Icon, type IconName } from "@/components/ui/Icon";

export interface Step {
  icon: IconName;
  title: string;
  note?: string;
}

/** Horizontal "A → B → C" diagram. Used to explain a pipeline without a paragraph. */
export function Steps({ steps, active }: { steps: Step[]; active?: number }) {
  return (
    <ol className="steps">
      {steps.map((s, i) => (
        <Fragment key={s.title}>
          {i > 0 && (
            <li className="steps-arrow" aria-hidden>
              <Icon name="arrowRight" size={16} />
            </li>
          )}
          <li className={`step${active === i ? " step-active" : ""}`}>
            <span className="step-icon">
              <Icon name={s.icon} size={18} />
            </span>
            <span>
              <strong>{s.title}</strong>
              {s.note && <span className="muted small">{s.note}</span>}
            </span>
          </li>
        </Fragment>
      ))}
    </ol>
  );
}
