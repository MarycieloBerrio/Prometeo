import Link from "next/link";
import type { ReactNode } from "react";

import type { Trial } from "@prometeo/contracts";

import { SourceLine } from "@/components/trials/SourceLine";
import { DataQualityBadge } from "@/components/ui/Badges";
import { Icon } from "@/components/ui/Icon";
import { formatQuantity, humanize, PHENOMENON_ICON } from "@/domain/format";

export function TrialCard({
  trial,
  selected = false,
  action,
}: {
  trial: Trial;
  selected?: boolean;
  action?: ReactNode;
}) {
  const headline = trial.results[0];
  return (
    <article className={"trial-card" + (selected ? " card-selected" : "")}>
      <div className="trial-card-top">
        <span className="mono">RECORD / {trial.id}</span>
        {trial.is_synthetic ? <DataQualityBadge quality="synthetic" /> : <span className="trial-origin">{trial.investigation}</span>}
      </div>

      <div className="trial-card-title">
        <div>
          <p className="eyebrow">MATERIAL / {humanize(trial.geometry)}</p>
          <h3><Link href={"/explorer/" + encodeURIComponent(trial.id)}>{trial.material}</Link></h3>
          <span className="small muted">{trial.investigation} · {trial.sample_id ? "sample " + trial.sample_id : "sample not recorded"}</span>
        </div>
        <span className="trial-sigil" aria-hidden="true"><Icon name="flame" size={26} /></span>
      </div>

      <dl className="trial-conditions">
        <div><dt>O₂</dt><dd>{formatQuantity(trial.oxygen) ?? "Not recorded"}</dd></div>
        <div><dt>FLOW</dt><dd>{formatQuantity(trial.flow_speed) ?? "Not recorded"}</dd></div>
        <div><dt>DIRECTION</dt><dd>{trial.flow_direction === "unknown" ? "Not recorded" : humanize(trial.flow_direction)}</dd></div>
        <div><dt>GEOMETRY</dt><dd>{humanize(trial.geometry)}</dd></div>
      </dl>

      <div className="phenomena">
        {trial.phenomena.length === 0 && <span className="small muted">Phenomena not recorded</span>}
        {trial.phenomena.map((phenomenon) => (
          <span key={phenomenon} className="phenomenon" title={"Recorded phenomenon: " + phenomenon}>
            <Icon name={PHENOMENON_ICON[phenomenon] ?? "info"} size={13} />
            {humanize(phenomenon)}
          </span>
        ))}
      </div>

      <div className="trial-card-result">
        <span className="small muted">RECORDED RESULT</span>
        {headline ? (
          <>
            <div className="trial-card-value">
              <span>{humanize(headline.name)}</span>
              <strong>{formatQuantity(headline.value)}</strong>
            </div>
            <DataQualityBadge quality={headline.quality} />
            <SourceLine provenance={headline.provenance} />
          </>
        ) : <strong className="muted small">No result recorded</strong>}
      </div>

      <details className="trial-quickview">
        <summary>Quick inspection <Icon name="plus" size={15} /></summary>
        <dl>
          <div><dt>Thickness</dt><dd>{formatQuantity(trial.thickness) ?? "Not recorded"}</dd></div>
          <div><dt>Thermal regime</dt><dd>{humanize(trial.thermal_regime)}</dd></div>
          <div><dt>Pressure</dt><dd>{formatQuantity(trial.pressure) ?? "Not recorded"}</dd></div>
          <div><dt>Media</dt><dd>{trial.media.length ? trial.media.length + " record(s)" : "None recorded"}</dd></div>
        </dl>
        {trial.notes && <p className="small muted">{trial.notes}</p>}
      </details>

      <div className="trial-card-foot">
        <SourceLine provenance={trial.provenance} />
        {action}
      </div>
    </article>
  );
}
