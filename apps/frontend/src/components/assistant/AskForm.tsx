import Form from "next/form";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { FLOW_DIRECTIONS, GEOMETRIES, humanize } from "@/domain/format";

export interface AskParams {
  q?: string;
  material?: string;
  geometry?: string;
  flow_direction?: string;
}

const SUGGESTIONS = [
  "How does flame spread over a solid change with ventilation speed in microgravity?",
  "At what airflow do flames over thin fuels extinguish?",
  "How does oxygen concentration affect flame spread rate?",
];

export function AskForm({ params }: { params: AskParams }) {
  const hasScope = Boolean(params.material || params.geometry || params.flow_direction);
  return (
    <Form action="/assistant" className="ask card">
      <label className="field field-grow ask-input">
        <Icon name="chat" size={18} />
        <input
          name="q"
          placeholder="Ask about fuels, oxygen, airflow, flame spread…"
          defaultValue={params.q}
          aria-label="Question"
          required
        />
        <button type="submit" className="btn btn-primary">
          Ask
          <Icon name="arrowRight" size={16} />
        </button>
      </label>

      <details className="ask-scope" open={hasScope}>
        <summary className="small">
          <Icon name="search" size={14} /> Narrow to specific conditions
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
          <span className="small muted">Try</span>
          {SUGGESTIONS.map((s) => (
            <Link key={s} href={{ pathname: "/assistant", query: { q: s } }} className="suggestion">
              {s}
            </Link>
          ))}
        </div>
      )}
    </Form>
  );
}
