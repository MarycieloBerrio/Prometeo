"use client";

import Link from "next/link";
import { useState } from "react";

import type { Trial } from "@prometeo/contracts";

import { SourceLine } from "@/components/trials/SourceLine";
import { DataQualityBadge } from "@/components/ui/Badges";
import { Icon } from "@/components/ui/Icon";
import { formatQuantity, humanize } from "@/domain/format";

const MAX = 2;

/** Selection stays local to the index; the gateway remains the source of trial data. */
export function TrialPicker({ trials }: { trials: Trial[] }) {
  const [activeId, setActiveId] = useState(trials[0]?.id ?? "");
  const [picked, setPicked] = useState<string[]>([]);
  const active = trials.find((trial) => trial.id === activeId) ?? trials[0];

  function toggle(id: string) {
    setPicked((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id].slice(-MAX),
    );
  }

  const ready = picked.length === MAX;
  const compareHref = "/compare?a=" + encodeURIComponent(picked[0] ?? "") + "&b=" + encodeURIComponent(picked[1] ?? "");

  return (
    <>
      <div className="index-workbench">
        <section className="index-ledger" aria-label="Experiment index">
          <div className="index-ledger-head">
            <span className="eyebrow">CONDITION POINTS / SELECT TO INSPECT</span>
            <span className="small muted">{trials.length} records</span>
          </div>
          <div className="index-columns" aria-hidden="true">
            <span>RECORD / MATERIAL</span><span>O₂</span><span>VENTILATION</span><span>RESULT</span><span>PAIR</span>
          </div>
          <ul className="index-rows">
            {trials.map((trial) => {
              const selected = active.id === trial.id;
              const on = picked.includes(trial.id);
              const result = trial.results.find((item) => item.name === "flame_spread_rate") ?? trial.results[0];
              return (
                <li key={trial.id} className={"index-row" + (selected ? " index-row-active" : "")}>
                  <button
                    type="button"
                    className="index-row-inspect"
                    aria-label={"Inspect " + trial.id}
                    aria-pressed={selected}
                    onClick={() => setActiveId(trial.id)}
                  >
                    <span className="index-row-identity"><strong>{trial.id}</strong><small>{trial.material} · {trial.sample_id ?? "sample unknown"} · {humanize(trial.geometry)}</small></span>
                    <span className="index-row-measure" data-label="O₂">{formatQuantity(trial.oxygen) ?? "—"}</span>
                    <span className="index-row-measure" data-label="FLOW">{formatQuantity(trial.flow_speed) ?? "—"}</span>
                    <span className="index-row-measure" data-label="RESULT">{result ? formatQuantity(result.value) : "—"}</span>
                  </button>
                  <button
                    type="button"
                    className={"index-row-pick" + (on ? " index-row-picked" : "")}
                    aria-label={(on ? "Remove " : "Add ") + trial.id + (on ? " from" : " to") + " comparison"}
                    aria-pressed={on}
                    onClick={() => toggle(trial.id)}
                  >
                    <Icon name={on ? "check" : "plus"} size={16} />
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="index-ledger-note">These are recorded condition points. Several may come from the same physical sample; rows are not independent replicate ignitions.</p>
        </section>

        <aside className="index-inspector" aria-label="Selected experiment">
          <div className="index-inspector-head"><span className="eyebrow">RECORD IN FOCUS</span><span className="mono small">{active.id}</span></div>
          <TrialInspector trial={active} />
        </aside>
      </div>

      <div className="tray" role="status">
        <div className="tray-intro"><span className="eyebrow">COMPARISON QUEUE</span><strong>{picked.length} / 2 selected</strong></div>
        <div className="tray-slots">
          {[0, 1].map((index) => (
            <span key={index} className={"slot" + (picked[index] ? " slot-filled" : "")}>
              <span className="slot-letter">{index === 0 ? "A" : "B"}</span>
              <span className="mono small">{picked[index] ?? "Awaiting record"}</span>
            </span>
          ))}
        </div>
        {ready ? (
          <Link href={compareHref} className="btn btn-primary">Compare selected <Icon name="arrowRight" size={16} /></Link>
        ) : (
          <span className="btn btn-primary btn-disabled" aria-disabled>Pick {MAX - picked.length} more</span>
        )}
      </div>
    </>
  );
}

function TrialInspector({ trial }: { trial: Trial }) {
  const result = trial.results.find((item) => item.name === "flame_spread_rate") ?? trial.results[0];
  return (
    <div className="record-inspection">
      <div className="record-inspection-title">
        <span className="eyebrow">{trial.investigation} / {humanize(trial.geometry)}</span>
        <h2>{trial.material}</h2>
        <p>{trial.sample_id ? `Sample ${trial.sample_id}` : "Sample not recorded"}</p>
      </div>
      <dl className="record-inspection-conditions">
        <div><dt>Oxygen</dt><dd>{formatQuantity(trial.oxygen) ?? "Not recorded"}</dd></div>
        <div><dt>Ventilation</dt><dd>{formatQuantity(trial.flow_speed) ?? "Not recorded"}</dd></div>
        <div><dt>Flow direction</dt><dd>{humanize(trial.flow_direction)}</dd></div>
      </dl>
      <div className="record-inspection-result">
        <span className="eyebrow">RECORDED RESULT</span>
        {result ? (
          <>
            <span>{humanize(result.name)}</span>
            <strong>{formatQuantity(result.value) ?? "Not recorded"}</strong>
            <DataQualityBadge quality={result.quality} />
            <SourceLine provenance={result.provenance} />
          </>
        ) : <p>No result recorded for this condition point.</p>}
      </div>
      {trial.is_synthetic && <DataQualityBadge quality="synthetic" />}
      <div className="record-inspection-source"><span className="eyebrow">RECORD SOURCE</span><SourceLine provenance={trial.provenance} /></div>
      <Link href={"/explorer/" + encodeURIComponent(trial.id)} className="record-inspection-link">
        Open full record <Icon name="arrowRight" size={16} />
      </Link>
    </div>
  );
}
