"use client";

import Link from "next/link";
import { useState } from "react";

import type { CoverageResponse } from "@prometeo/contracts";

import { Icon } from "@/components/ui/Icon";

type Cell = CoverageResponse["cells"][number];
const percent = (fraction: number) => Number((fraction * 100).toPrecision(4)) + "%";
const keyOf = (cell: Cell) => cell.oxygen_range[0] + "/" + cell.flow_range_cm_s[0];

/** Every cell is selectable; absence remains a documented data gap. */
export function CoverageMap({ coverage, highlight = [] }: { coverage: CoverageResponse; highlight?: string[] }) {
  const flowBins = coverage.flow_edges_cm_s.length - 1;
  const oxygenBins = coverage.oxygen_edges.length - 1;
  const first = coverage.cells.find((cell) => cell.has_evidence) ?? coverage.cells[0];
  const [selectedKey, setSelectedKey] = useState(first ? keyOf(first) : "");
  if (flowBins < 1 || oxygenBins < 1 || !first) {
    return <p className="muted">No recorded evidence is mapped to oxygen and airflow intervals.</p>;
  }
  const selected = coverage.cells.find((cell) => keyOf(cell) === selectedKey) ?? first;
  const rows = Array.from({ length: oxygenBins }, (_, index) =>
    coverage.cells.slice(index * flowBins, (index + 1) * flowBins),
  ).reverse();

  return (
    <figure className="coverage">
      <div className="coverage-workbench">
        <div>
          <div className="coverage-body">
            <span className="coverage-ylabel"><Icon name="oxygen" size={15} /> Oxygen</span>
            <div className="coverage-grid" style={{ gridTemplateColumns: "auto repeat(" + flowBins + ", minmax(56px, 1fr))" }}>
              {rows.map((row) => (
                <Row key={row[0].oxygen_range.join("-")} cells={row} highlight={highlight} selectedKey={keyOf(selected)} onSelect={setSelectedKey} />
              ))}
              <span />
              {coverage.cells.slice(0, flowBins).map((cell) => (
                <span key={cell.flow_range_cm_s.join("-")} className="coverage-axis">
                  {cell.flow_range_cm_s[0]}–{cell.flow_range_cm_s[1]}
                </span>
              ))}
            </div>
          </div>
          <p className="coverage-xlabel"><Icon name="wind" size={15} /> Airflow (cm/s)</p>
        </div>
        <aside className="coverage-inspector" aria-live="polite">
          <span className="eyebrow">SELECTED EVIDENCE CELL</span>
          <div className="coverage-inspector-reading">
            <div><small>OXYGEN</small><strong>{percent(selected.oxygen_range[0])}–{percent(selected.oxygen_range[1])}</strong></div>
            <div><small>AIRFLOW</small><strong>{selected.flow_range_cm_s[0]}–{selected.flow_range_cm_s[1]} <em>cm/s</em></strong></div>
          </div>
          <strong className={"coverage-inspector-status" + (selected.has_evidence ? " has-evidence" : "")}>
            {selected.has_evidence ? selected.trial_ids.length + " recorded condition point(s)" : "No recorded evidence"}
          </strong>
          {selected.has_evidence ? (
            <ul className="coverage-trials">
              {selected.trial_ids.map((id) => (
                <li key={id}><Link href={"/explorer/" + encodeURIComponent(id)}>{id} <Icon name="arrowRight" size={13} /></Link></li>
              ))}
            </ul>
          ) : <p className="small muted">This gap says nothing about material safety or behavior outside the recorded range.</p>}
          {selected.observed.length > 0 && <p className="small muted">Observed: {selected.observed.join(", ")}</p>}
        </aside>
      </div>
      <figcaption className="legend">
        <span><i className="swatch swatch-on" /> Trials recorded</span>
        <span><i className="swatch swatch-off" /> No recorded evidence (not “safe”)</span>
        {highlight.length > 0 && <span><i className="swatch swatch-hl" /> Selected trials</span>}
      </figcaption>
      {coverage.unplaced_trial_ids.length > 0 && (
        <p className="muted small">{coverage.unplaced_trial_ids.length} trial(s) not on the map: oxygen or airflow not recorded, or out of range.</p>
      )}
    </figure>
  );
}

function Row({ cells, highlight, selectedKey, onSelect }: {
  cells: Cell[];
  highlight: string[];
  selectedKey: string;
  onSelect: (key: string) => void;
}) {
  const [low, high] = cells[0].oxygen_range;
  return (
    <>
      <span className="coverage-axis coverage-axis-y">{percent(low)}–{percent(high)}</span>
      {cells.map((cell) => {
        const marked = cell.trial_ids.some((id) => highlight.includes(id));
        const label = cell.has_evidence ? cell.trial_ids.length + " trial(s): " + cell.trial_ids.join(", ") : "No recorded evidence";
        return (
          <button
            type="button"
            key={keyOf(cell)}
            className={"cell" + (cell.has_evidence ? " cell-on" : "") + (marked ? " cell-hl" : "") + (selectedKey === keyOf(cell) ? " cell-selected" : "")}
            aria-label={"Oxygen " + percent(low) + " to " + percent(high) + ", airflow " + cell.flow_range_cm_s[0] + " to " + cell.flow_range_cm_s[1] + " cm/s: " + label}
            aria-pressed={selectedKey === keyOf(cell)}
            onClick={() => onSelect(keyOf(cell))}
          >
            {cell.has_evidence ? cell.trial_ids.length : "—"}
          </button>
        );
      })}
    </>
  );
}
