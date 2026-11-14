import Form from "next/form";
import Link from "next/link";

import type { TrialQuery } from "@/application/ports/evidence-gateway";
import { Icon, type IconName } from "@/components/ui/Icon";
import { FLOW_DIRECTIONS, GEOMETRIES, humanize, INVESTIGATIONS, PHENOMENA } from "@/domain/format";

export function TrialFilters({ query }: { query: TrialQuery }) {
  const hasFilters = Object.values(query).some(Boolean);
  return (
    <Form action="/explorer" className="filters">
      <Select name="investigation" icon="book" label="Investigation" options={INVESTIGATIONS} value={query.investigation} />
      <label className="field field-grow">
        <Icon name="flame" size={16} />
        <input name="material" placeholder="Fuel, e.g. PMMA" defaultValue={query.material} aria-label="Fuel" />
      </label>
      <Select name="geometry" icon="box" label="Geometry" options={GEOMETRIES} value={query.geometry} />
      <Select
        name="flow_direction"
        icon="wind"
        label="Airflow"
        options={FLOW_DIRECTIONS}
        value={query.flow_direction}
      />
      <Select name="phenomenon" icon="zap" label="Phenomenon" options={PHENOMENA} value={query.phenomenon} />
      <button type="submit" className="btn btn-primary">
        <Icon name="search" size={16} />
        Search
      </button>
      {hasFilters && (
        <Link href="/explorer" className="btn btn-ghost">
          Clear
        </Link>
      )}
    </Form>
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
    <label className="field">
      <Icon name={icon} size={16} />
      <select name={name} defaultValue={value ?? ""} aria-label={label}>
        <option value="">{label}: any</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {humanize(o)}
          </option>
        ))}
      </select>
    </label>
  );
}
