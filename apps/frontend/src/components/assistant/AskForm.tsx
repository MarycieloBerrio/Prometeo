import Form from "next/form";
import Link from "next/link";

import type { AssistantModel } from "@prometeo/contracts";

import { AskPendingNotice, AskSubmit, LinkPendingMark } from "@/components/assistant/AskStatus";
import { Icon } from "@/components/ui/Icon";
import { FLOW_DIRECTIONS, GEOMETRIES, humanize } from "@/domain/format";

export interface AskParams {
  q?: string;
  material?: string;
  geometry?: string;
  flow_direction?: string;
  model?: string;
}

const SUGGESTIONS = [
  "How does flame spread over a solid change with ventilation speed in microgravity?",
  "At what airflow do flames over thin fuels extinguish?",
  "How does oxygen concentration affect flame spread rate?",
];

export function AskForm({
  params,
  models = [],
  defaultModel = null,
}: {
  params: AskParams;
  /** Models that can write the interpretation; empty when the engine uses none. */
  models?: AssistantModel[];
  defaultModel?: string | null;
}) {
  const model = models.some((m) => m.id === params.model) ? params.model : (defaultModel ?? undefined);
  return (
    <Form action="/assistant" className="ask">
      <p className="eyebrow">ASK THE EVIDENCE</p>
      <div className="field field-grow ask-input">
        <Icon name="search" size={18} />
        <input
          name="q"
          placeholder="e.g. How does ventilation affect flame spread in microgravity?"
          defaultValue={params.q}
          aria-label="Question"
          required
        />
        {models.length > 0 && (
          <label className="ask-model" title="Model that writes the interpretation. Facts and limitations never depend on it.">
            <span>Model</span>
            <select name="model" defaultValue={model} aria-label="Model that writes the interpretation">
              {models.map((m) => (
                <option key={m.id} value={m.id} title={m.description}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <AskSubmit />
      </div>
      <AskPendingNotice />

      <details className="ask-scope" open>
        <summary className="small">
          <Icon name="layers" size={14} /> Constrain the evidence search
        </summary>
        <div className="filters">
          <label className="field">
            <Icon name="flame" size={16} />
            <input name="material" placeholder="Fuel" defaultValue={params.material} aria-label="Fuel" />
          </label>
          <label className="field">
            <Icon name="box" size={16} />
            <select name="geometry" defaultValue={params.geometry ?? ""} aria-label="Geometry">
              <option value="">Geometry: any</option>
              {GEOMETRIES.map((g) => (
                <option key={g} value={g}>
                  {humanize(g)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <Icon name="wind" size={16} />
            <select name="flow_direction" defaultValue={params.flow_direction ?? ""} aria-label="Airflow">
              <option value="">Airflow: any</option>
              {FLOW_DIRECTIONS.map((d) => (
                <option key={d} value={d}>
                  {humanize(d)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </details>

      {!params.q && (
        <div className="suggestions">
          <span className="eyebrow">START WITH A QUESTION</span>
          {SUGGESTIONS.map((s) => (
            <Link key={s} href={{ pathname: "/assistant", query: { q: s } }} className="suggestion">
              {s}
              <LinkPendingMark />
            </Link>
          ))}
        </div>
      )}
    </Form>
  );
}
