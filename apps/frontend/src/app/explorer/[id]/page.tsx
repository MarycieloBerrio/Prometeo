import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import type { Trial } from "@prometeo/contracts";

import { ConditionTiles } from "@/components/trials/Conditions";
import { SourceLine } from "@/components/trials/SourceLine";
import { DataQualityBadge, Tag } from "@/components/ui/Badges";
import { ApiDown } from "@/components/ui/Callout";
import { DemoBanner } from "@/components/ui/DemoBanner";
import { Icon } from "@/components/ui/Icon";
import { Section } from "@/components/ui/PageHeader";
import { formatQuantity, humanize, mediaUrl, PHENOMENON_ICON } from "@/domain/format";
import { gateway } from "@/infrastructure/gateway";
import { ApiError } from "@/infrastructure/http/http-evidence-gateway";

type Params = PageProps<"/explorer/[id]">["params"];

export default function TrialPage({ params }: PageProps<"/explorer/[id]">) {
  return (
    <div className="page">
      <Link href="/explorer" className="back">
        <Icon name="search" size={15} />
        All trials
      </Link>
      <Suspense fallback={<p className="muted">Loading trial…</p>}>
        <TrialSheet params={params} />
      </Suspense>
    </div>
  );
}

async function TrialSheet({ params }: { params: Params }) {
  const { id } = await params;
  const trialId = decodeURIComponent(id);

  let trial: Trial;
  try {
    trial = await gateway.getTrial(trialId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    return <ApiDown message={e instanceof Error ? e.message : "Unknown error"} />;
  }

  return (
    <>
      <header className="page-header">
        <span className="page-icon">
          <Icon name="flame" size={24} />
        </span>
        <div>
          <p className="mono small muted">{trial.id}</p>
          <h1>{trial.material}</h1>
          <div className="row">
            <Tag>{trial.investigation}</Tag>
            {trial.sample_id && <span className="muted small">Sample {trial.sample_id}</span>}
            {trial.phenomena.map((p) => (
              <span key={p} className="phenomenon">
                <Icon name={PHENOMENON_ICON[p] ?? "info"} size={13} />
                {humanize(p)}
              </span>
            ))}
          </div>
        </div>
        <div className="page-actions">
          <Link href={`/compare?a=${encodeURIComponent(trial.id)}`} className="btn btn-primary">
            <Icon name="compare" size={16} />
            Compare with…
          </Link>
        </div>
      </header>

      {trial.is_synthetic && (
        <DemoBanner />
      )}

      <Section title="Conditions">
        <ConditionTiles trial={trial} />
      </Section>

      <Section title="Results" hint="Each value shows its data quality and source">
        {trial.results.length === 0 ? (
          <p className="muted">No results recorded for this trial.</p>
        ) : (
          <ul className="list">
            {trial.results.map((r) => (
              <li key={r.name} className="list-row">
                <div>
                  <span className="small muted">{humanize(r.name)}</span>
                  <div className="row">
                    <strong className="big">{formatQuantity(r.value)}</strong>
                    {r.uncertainty && <span className="muted">± {formatQuantity(r.uncertainty)}</span>}
                    <DataQualityBadge quality={r.quality} />
                  </div>
                  {r.method && <span className="small muted">Method: {r.method}</span>}
                </div>
                <SourceLine provenance={r.provenance} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      {trial.media.length > 0 && (
        <Section title="Media">
          <ul className="list">
            {trial.media.map((m) => (
              <li key={m.uri} className="list-row">
                <span className="row">
                  <Icon name="video" size={16} />
                  {mediaUrl(m.uri) ? (
                    <a className="link mono small" href={mediaUrl(m.uri) ?? undefined} target="_blank" rel="noreferrer">
                      Open {m.kind} source
                    </a>
                  ) : (
                    <span className="mono small">URI unavailable or unverified</span>
                  )}
                </span>
                <Tag>{m.kind}</Tag>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Source">
        <SourceLine provenance={trial.provenance} />
        {trial.notes && <p className="muted small">{trial.notes}</p>}
      </Section>
    </>
  );
}
