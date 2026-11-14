import Form from "next/form";

import type { Trial } from "@prometeo/contracts";

import { Icon } from "@/components/ui/Icon";
import { humanize, VARIABLES } from "@/domain/format";

/** The variables a user most often changes on purpose between two trials. */
const VARIED_CHOICES = ["flow_speed", "oxygen", "thickness", "pressure"];

export function CompareForm({
  trials,
  a,
  b,
  varied,
  metric,
}: {
  trials: Trial[];
  a?: string;
  b?: string;
  varied: string[];
  metric: string;
}) {
  const metrics = [...new Set(trials.flatMap((trial) => trial.results.map((result) => result.name)))];
  if (!metrics.includes("flame_spread_rate")) metrics.unshift("flame_spread_rate");
  return (
    <Form action="/compare" className="compare-form card">
      <input type="hidden" name="submitted" value="1" />
      <div className="compare-pick">
        <TrialSelect name="a" letter="A" trials={trials} value={a} />
        <span className="compare-vs" aria-hidden>
          <Icon name="compare" size={20} />
        </span>
        <TrialSelect name="b" letter="B" trials={trials} value={b} />
      </div>

      <fieldset className="varied">
        <legend className="small muted">What changed on purpose?</legend>
        {VARIABLES.filter((v) => VARIED_CHOICES.includes(v.key)).map((v) => (
          <label key={v.key} className="toggle">
            <input type="checkbox" name="varied" value={v.key} defaultChecked={varied.includes(v.key)} />
            <span>
              <Icon name={v.icon} size={15} />
              {v.label}
            </span>
          </label>
        ))}
      </fieldset>

      <label className="field compare-metric">
        <Icon name="chart" size={16} />
        <span className="small">Result</span>
        <select name="metric" defaultValue={metric} aria-label="Result metric">
          {metrics.map((name) => <option key={name} value={name}>{humanize(name)}</option>)}
        </select>
      </label>

      <button type="submit" className="btn btn-primary" disabled={trials.length < 2}>
        Compare
        <Icon name="arrowRight" size={16} />
      </button>
    </Form>
  );
}

function TrialSelect({
  name,
  letter,
  trials,
  value,
}: {
  name: string;
  letter: string;
  trials: Trial[];
  value?: string;
}) {
  return (
    <label className="field field-grow">
      <span className="slot-letter">{letter}</span>
      <select name={name} defaultValue={value ?? ""} aria-label={`Trial ${letter}`} required>
        <option value="" disabled>
          Pick trial {letter}
        </option>
        {trials.map((t) => (
          <option key={t.id} value={t.id}>
            {t.id} · {t.material}
          </option>
        ))}
      </select>
    </label>
  );
}
