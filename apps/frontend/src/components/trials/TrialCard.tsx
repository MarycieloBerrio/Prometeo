import Link from "next/link";
import type { ReactNode } from "react";

import type { Trial } from "@prometeo/contracts";

import { ConditionChips } from "@/components/trials/Conditions";
import { DataQualityBadge, Tag } from "@/components/ui/Badges";
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
    <article className={`card trial-card${selected ? " card-selected" : ""}`}>
      <div className="row-between">
        <span className="mono small muted">{trial.id}</span>
        {trial.is_synthetic ? <DataQualityBadge quality="synthetic" /> : <Tag>{trial.investigation}</Tag>}
      </div>

      <h3>
        <Link href={`/explorer/${encodeURIComponent(trial.id)}`}>{trial.material}</Link>
      </h3>

      <ConditionChips trial={trial} />

      <div className="phenomena">
        {trial.phenomena.map((p) => (
          <span key={p} className="phenomenon" title={`Observed: ${p}`}>
            <Icon name={PHENOMENON_ICON[p] ?? "info"} size={13} />
            {humanize(p)}
          </span>
        ))}
      </div>

      <div className="row-between card-foot">
        {headline ? (
          <span className="result">
            <span className="small muted">{humanize(headline.name)}</span>
            <strong>{formatQuantity(headline.value)}</strong>
            <DataQualityBadge quality={headline.quality} />
          </span>
        ) : (
          <span className="small muted">No results recorded</span>
        )}
        {action}
      </div>
    </article>
  );
}
