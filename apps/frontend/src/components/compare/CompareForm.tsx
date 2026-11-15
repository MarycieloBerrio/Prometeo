"use client";

import { type MouseEvent, useState } from "react";
import { flushSync } from "react-dom";

import type { Trial } from "@prometeo/contracts";

import { Icon } from "@/components/ui/Icon";
import { formatQuantity, humanize, VARIABLES } from "@/domain/format";

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
  const [selectedA, setSelectedA] = useState(a ?? "");
  const [selectedB, setSelectedB] = useState(b ?? "");
  const sameTrial = Boolean(selectedA && selectedB && selectedA === selectedB);

  function swap(event: MouseEvent<HTMLButtonElement>) {
    const form = event.currentTarget.form;
    // Commit the swapped selection before submitting, so the form sends the new order.
    flushSync(() => {
      setSelectedA(selectedB);
      setSelectedB(selectedA);
    });
    // With both records chosen the comparison is re-run at once: A and B label every result.
    if (selectedA && selectedB && !sameTrial) form?.requestSubmit();
  }
  const metrics = [...new Set(trials.flatMap((trial) => trial.results.map((result) => result.name)))];
  if (!metrics.includes("flame_spread_rate")) metrics.unshift("flame_spread_rate");
  // Native GET form: next/form was triggering a CompareForm hydration mismatch under Cache Components.
  return (
    <form action="/compare" method="get" className="compare-form card">
      <input type="hidden" name="submitted" value="1" />
      <div className="compare-form-heading"><div><p className="eyebrow">EXPERIMENTAL SETUP / A : B</p><h2>Build a physical comparison</h2></div><p className="small muted">Select two records. Declare what changed; the remaining conditions are checked by the Evidence Engine.</p></div>
      <div className="compare-pick">
        <TrialSelect name="a" letter="A" trials={trials} value={selectedA} onSelect={setSelectedA} />
        <button
          type="button"
          className="compare-vs"
          onClick={swap}
          disabled={!selectedA && !selectedB}
          aria-label="Swap trial A and trial B"
          title="Swap trial A and trial B"
        >
          <Icon name="compare" size={20} />
        </button>
        <TrialSelect name="b" letter="B" trials={trials} value={selectedB} onSelect={setSelectedB} />
      </div>
      {sameTrial && <p className="compare-selection-warning" role="alert">Choose two different records to run a comparison.</p>}

      <fieldset className="varied">
        <legend>ISOLATED VARIABLE(S) <span className="small muted">What changed on purpose?</span></legend>
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

      <div className="compare-form-footer">
        <label className="compare-metric">
          <span className="eyebrow">RECORDED METRIC</span>
          <span className="field"><Icon name="chart" size={16} /><select name="metric" defaultValue={metric} aria-label="Result metric">
            {metrics.map((name) => <option key={name} value={name}>{humanize(name)}</option>)}
          </select></span>
        </label>
        <button type="submit" className="btn btn-primary" disabled={trials.length < 2 || sameTrial}>
          Run physics check <Icon name="arrowRight" size={16} />
        </button>
      </div>
    </form>
  );
}

function TrialSelect({
  name,
  letter,
  trials,
  value,
  onSelect,
}: {
  name: string;
  letter: string;
  trials: Trial[];
  value?: string;
  onSelect: (value: string) => void;
}) {
  const chosen = trials.find((trial) => trial.id === value);
  return (
    <label className="compare-select">
      <span className="compare-select-heading"><span className="slot-letter">{letter}</span><span>TRIAL {letter} / SOURCE RECORD</span></span>
      <select name={name} value={value ?? ""} onChange={(event) => onSelect(event.target.value)} aria-label={`Trial ${letter}`} required>
        <option value="" disabled>
          Pick trial {letter}
        </option>
        {trials.map((t) => (
          <option key={t.id} value={t.id}>
            {t.id} · {t.material}
          </option>
        ))}
      </select>
      <span className="compare-select-meta">{chosen ? `${chosen.investigation} · ${chosen.material} · ${chosen.geometry}` : "Select a record from the evidence index"}</span>
      {chosen && <dl className="compare-select-preview"><div><dt>O₂</dt><dd>{formatQuantity(chosen.oxygen) ?? "Unknown"}</dd></div><div><dt>FLOW</dt><dd>{formatQuantity(chosen.flow_speed) ?? "Unknown"}</dd></div><div><dt>DIRECTION</dt><dd>{humanize(chosen.flow_direction)}</dd></div></dl>}
    </label>
  );
}
