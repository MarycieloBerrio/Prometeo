import Link from "next/link";

import type { AskResponse } from "@prometeo/contracts";

import { EvidenceSources } from "@/components/assistant/EvidenceSources";
import { Group } from "@/components/assistant/Group";
import { TierBadge } from "@/components/ui/Badges";
import { Icon } from "@/components/ui/Icon";

const TIER_TONE: Record<string, string> = { direct: "ok", partial: "warn", insufficient: "danger" };

/** Answer first, evidence behind it in collapsible groups so the page stays short. */
export function AnswerPanel({ response }: { response: AskResponse }) {
  const refused = response.answer === null;
  return (
    <div className="answer">
      <div className={`answer-main card tone-border-${TIER_TONE[response.tier] ?? "neutral"}${refused ? " answer-refusal" : ""}`}>
        <div className="answer-topline"><span className="eyebrow">RESEARCH OUTPUT / EVIDENCE TIER</span>
          <TierBadge tier={response.tier} />
          {response.model && <span className="small muted mono">{response.model}</span>}
        </div>
        {refused ? (
          <>
            <h2>
              <Icon name="ban" size={20} /> The available evidence cannot answer this
            </h2>
            <p>{response.refusal_reason ?? "No supported conclusion is available for this question."}</p>
          </>
        ) : (
          <>
            <p className="eyebrow">{response.model ? "AI EXPLANATION" : "EVIDENCE ENGINE EXPLANATION"} / REVIEW THE SOURCES BELOW</p>
            <p className="answer-text">{response.answer}</p>
          </>
        )}
        <div className="answer-tally"><span>{response.assessments.length} trials assessed</span><span>{response.cited_sources.length} cited sources</span><span>{response.limitations.length} limitations</span></div>
      </div>

      <div className="answer-section-label"><span className="eyebrow">TRACE THE RESPONSE</span><span className="small muted">Open each register to inspect its basis</span></div>

      <EvidenceSources sources={response.cited_sources} documents={response.documents} />

      <Group icon="alert" title="Limits of this answer" count={response.limitations.length}>
        <ul className="bullets">
          {response.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Group>

      <Group icon="search" title="Experimental evidence · trials assessed" count={response.assessments.length}>
        <ul className="list">
          {response.assessments.map((a) => {
            // A trial can rate well on its own and still be left out of the interpretation
            // because no other usable trial is comparable with it. Showing its own tier as
            // the headline would read as "this answer relies on it".
            const excluded = !refused && a.tier !== "insufficient" && !a.in_interpretation;
            return (
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
                  {excluded && (
                    <div className="small muted">
                      No comparable counterpart among the usable trials, so it is excluded from
                      the interpretation. The rating above describes this trial alone.
                    </div>
                  )}
                </div>
                {excluded ? (
                  <span className="pill tone-neutral">
                    <Icon name="info" size={14} />
                    Not used in interpretation
                  </span>
                ) : (
                  <TierBadge tier={a.tier} />
                )}
              </li>
            );
          })}
        </ul>
      </Group>

      <Group icon="sigma" title="Computed facts · Evidence Engine" count={response.computed_facts.length}>
        <ul className="bullets mono small">
          {response.computed_facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </Group>
    </div>
  );
}
