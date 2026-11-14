import { Suspense } from "react";

import type { Trial } from "@prometeo/contracts";

import { DataQualityBadge } from "@/components/DataQualityBadge";
import { gateway } from "@/infrastructure/gateway";

type SearchParams = PageProps<"/explorer">["searchParams"];

export default function ExplorerPage({ searchParams }: PageProps<"/explorer">) {
  // Static shell renders immediately; request-time data streams in under <Suspense>.
  return (
    <section className="stack">
      <p className="eyebrow">Module 01</p>
      <h1>Experiment Explorer</h1>
      <Suspense fallback={<p className="muted">Loading trials…</p>}>
        <TrialResults searchParams={searchParams} />
      </Suspense>
    </section>
  );
}

async function TrialResults({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const material = typeof params.material === "string" ? params.material : undefined;

  let trials: Trial[] = [];
  let error: string | null = null;
  try {
    trials = await gateway.listTrials({ material });
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <>
      <form className="filters">
        <input name="material" placeholder="Material (e.g. PMMA)" defaultValue={material} />
        <button type="submit">Filter</button>
      </form>

      {error && <p className="notice">Could not reach the Evidence Engine API: {error}</p>}
      {!error && trials.length === 0 && (
        <p className="notice">
          No trials match. An empty result means no recorded evidence, not that a material is safe.
        </p>
      )}
      {trials.length > 0 && <TrialTable trials={trials} />}
    </>
  );
}

function fmt(q: Trial["oxygen"]): string {
  return q ? `${q.value} ${q.unit}` : "—";
}

function TrialTable({ trials }: { trials: Trial[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Trial</th>
          <th>Investigation</th>
          <th>Material</th>
          <th>Geometry</th>
          <th>O₂</th>
          <th>Flow</th>
          <th>Phenomena</th>
          <th>Results</th>
        </tr>
      </thead>
      <tbody>
        {trials.map((t) => (
          <tr key={t.id}>
            <td className="mono">{t.id}</td>
            <td>{t.investigation}</td>
            <td>{t.material}</td>
            <td>
              {t.geometry} · {t.thermal_regime}
            </td>
            <td>{fmt(t.oxygen)}</td>
            <td>
              {fmt(t.flow_speed)} · {t.flow_direction}
            </td>
            <td>{t.phenomena.join(", ")}</td>
            <td>
              {t.results.map((r) => (
                <div key={r.name}>
                  {r.name}: {r.value.value} {r.value.unit} <DataQualityBadge quality={r.quality} />
                </div>
              ))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
