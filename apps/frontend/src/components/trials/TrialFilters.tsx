import Form from "next/form";
import Link from "next/link";

import type { TrialQuery } from "@/application/ports/evidence-gateway";
import { Icon, type IconName } from "@/components/ui/Icon";
import { FLOW_DIRECTIONS, GEOMETRIES, humanize, INVESTIGATIONS, PHENOMENA } from "@/domain/format";

export function TrialFilters({ query }: { query: TrialQuery }) {
  const hasFilters = Object.values(query).some(Boolean);
  return (
    <section className="filter-panel" aria-label="Filter experiment records">
      <details className="filter-disclosure" open={hasFilters}>
        <summary>
          <span><Icon name="search" size={17} /> Filter recorded trials</span>
          <small>{hasFilters ? "Filters active" : "Material · investigation · geometry · flow"}</small>
          <Icon name="plus" size={17} />
        </summary>
        <Form action="/explorer" className="filter-grid">
        <label className="filter-field filter-material">
          <span>MATERIAL</span>
          <span className="field"><Icon name="flame" size={16} /><input name="material" placeholder="e.g. PMMA" defaultValue={query.material} aria-label="Material" /></span>
        </label>
        <Select name="investigation" icon="book" label="Investigation" options={INVESTIGATIONS} value={query.investigation} />
        <Select name="geometry" icon="box" label="Geometry" options={GEOMETRIES} value={query.geometry} />
        <Select name="flow_direction" icon="wind" label="Flow direction" options={FLOW_DIRECTIONS} value={query.flow_direction} />
        <Select name="phenomenon" icon="zap" label="Phenomenon" options={PHENOMENA} value={query.phenomenon} />
        <div className="filter-actions">
          <button type="submit" className="btn btn-primary"><Icon name="search" size={16} /> Search records</button>
          {hasFilters && <Link href="/explorer" className="btn btn-ghost">Reset</Link>}
        </div>
        </Form>
      </details>
    </section>
  );
}

function Select({
  name,
  icon,
  label,
  options,
  value,
}: {
  name: string;
  icon: IconName;
  label: string;
  options: readonly string[];
  value?: string;
}) {
  return (
    <label className="filter-field">
      <span>{label.toUpperCase()}</span>
      <span className="field">
        <Icon name={icon} size={16} />
        <select name={name} defaultValue={value ?? ""} aria-label={label}>
          <option value="">Any</option>
          {options.map((o) => (
            <option key={o} value={o}>
              {humanize(o)}
            </option>
          ))}
        </select>
      </span>
    </label>
  );
}
