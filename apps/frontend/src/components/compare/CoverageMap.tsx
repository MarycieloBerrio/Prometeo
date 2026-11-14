import type { CoverageResponse } from "@prometeo/contracts";

import { Icon } from "@/components/ui/Icon";

const percent = (fraction: number) => `${Math.round(fraction * 100)}%`;

/**
 * O₂ × airflow grid. A filled cell means trials exist there. An empty cell means
 * "no recorded evidence", never "safe".
 */
export function CoverageMap({ coverage, highlight = [] }: { coverage: CoverageResponse; highlight?: string[] }) {
  const flowBins = coverage.flow_edges_cm_s.length - 1;
  const oxygenBins = coverage.oxygen_edges.length - 1;
  // Cells arrive row-major by oxygen bin. Show the highest oxygen at the top, like a chart.
  const rows = Array.from({ length: oxygenBins }, (_, i) =>
    coverage.cells.slice(i * flowBins, (i + 1) * flowBins),
  ).reverse();

  return (
    <figure className="coverage">
      <div className="coverage-body">
        <span className="coverage-ylabel">
          <Icon name="oxygen" size={15} /> Oxygen
        </span>
        <div className="coverage-grid" style={{ gridTemplateColumns: `auto repeat(${flowBins}, minmax(56px, 1fr))` }}>
          {rows.map((row) => (
            <Row key={row[0].oxygen_range.join("-")} cells={row} highlight={highlight} />
          ))}
          <span />
          {coverage.cells.slice(0, flowBins).map((c) => (
            <span key={c.flow_range_cm_s.join("-")} className="coverage-axis">
              {c.flow_range_cm_s[0]}–{c.flow_range_cm_s[1]}
            </span>
          ))}
        </div>
      </div>
      <p className="coverage-xlabel">
        <Icon name="wind" size={15} /> Airflow (cm/s)
      </p>
      <figcaption className="legend">
        <span>
          <i className="swatch swatch-on" /> Trials recorded
        </span>
        <span>
          <i className="swatch swatch-off" /> No recorded evidence (not “safe”)
        </span>
        {highlight.length > 0 && (
          <span>
            <i className="swatch swatch-hl" /> Selected trials
          </span>
        )}
      </figcaption>
      {coverage.unplaced_trial_ids.length > 0 && (
        <p className="muted small">
          {coverage.unplaced_trial_ids.length} trial(s) not on the map: oxygen or airflow not recorded, or out of
          range.
        </p>
      )}
    </figure>
  );
}

function Row({ cells, highlight }: { cells: CoverageResponse["cells"]; highlight: string[] }) {
  const [low, high] = cells[0].oxygen_range;
  return (
    <>
      <span className="coverage-axis coverage-axis-y">
        {percent(low)}–{percent(high)}
      </span>
      {cells.map((c) => {
        const selected = c.trial_ids.some((id) => highlight.includes(id));
        const label = c.has_evidence
          ? `${c.trial_ids.length} trial(s): ${c.trial_ids.join(", ")}`
          : "No recorded evidence";
        return (
          <span
            key={c.flow_range_cm_s.join("-")}
            className={`cell${c.has_evidence ? " cell-on" : ""}${selected ? " cell-hl" : ""}`}
            title={label}
            aria-label={label}
          >
            {c.has_evidence ? c.trial_ids.length : ""}
          </span>
        );
      })}
    </>
  );
}
