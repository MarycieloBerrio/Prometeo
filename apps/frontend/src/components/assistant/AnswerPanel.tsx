import Link from "next/link";
import type { ReactNode } from "react";

import type { AskResponse } from "@prometeo/contracts";

import { SourceLine } from "@/components/trials/SourceLine";
import { TierBadge } from "@/components/ui/Badges";
import { Icon, type IconName } from "@/components/ui/Icon";

const TIER_TONE: Record<string, string> = { direct: "ok", partial: "warn", insufficient: "danger" };

/** Answer first, evidence behind it in collapsible groups so the page stays short. */
export function AnswerPanel({ response }: { response: AskResponse }) {
  const refused = response.answer === null;
  return (
    <div className="answer">
      <div className={`answer-main card tone-border-${TIER_TONE[response.tier] ?? "neutral"}`}>
        <div className="row-between">
          <TierBadge tier={response.tier} />
          {response.model && <span className="small muted mono">{response.model}</span>}
        </div>
        {refused ? (
          <>
            <h2>
              <Icon name="ban" size={20} /> Prometeo will not answer this
            </h2>
            <p>{response.refusal_reason}</p>
          </>
        ) : (
          <p className="answer-text">{response.answer}</p>
        )}
      </div>

      <Group icon="alert" title="Limits of this answer" count={response.limitations.length} open>
        <ul className="bullets">
          {response.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Group>

      <Group icon="search" title="Trials assessed" count={response.assessments.length}>
        <ul className="list">
          {response.assessments.map((a) => (
            <li key={a.trial_id} className="list-row">
              <div>
                <Link href={`/explorer/${encodeURIComponent(a.trial_id)}`} className="mono link">
                  {a.trial_id}
                </Link>
                <div className="small muted">
                  Relevance {a.relevance} · Quality {a.quality}
                </div>
                {a.reasons.map((r) => (
                  <div key={r} className="small muted">
                    {r}
                  </div>
                ))}
              </div>
              <TierBadge tier={a.tier} />
            </li>
          ))}
        </ul>
      </Group>

      <Group icon="sigma" title="Computed facts" count={response.computed_facts.length}>
        <ul className="bullets mono small">
          {response.computed_facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </Group>

      <Group icon="book" title="Documents" count={response.documents.length}>
        <ul className="list">
          {response.documents.map((d) => (
            <li key={d.id} className="list-col">
              <p className="small">“{d.excerpt}”</p>
              <SourceLine provenance={d.provenance} />
            </li>
          ))}
        </ul>
      </Group>
    </div>
  );
}

function Group({
  icon,
  title,
  count,
  open = false,
  children,
}: {
  icon: IconName;
  title: string;
  count: number;
  open?: boolean;
  children: ReactNode;
}) {
  if (count === 0) return null;
  return (
    <details className="group" open={open}>
      <summary>
        <Icon name={icon} size={16} />
        <span>{title}</span>
        <span className="count">{count}</span>
      </summary>
      <div className="group-body">{children}</div>
    </details>
  );
}
