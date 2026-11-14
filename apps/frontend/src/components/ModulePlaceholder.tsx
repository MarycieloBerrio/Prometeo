import { MODULES } from "@/domain/modules";

export function ModulePlaceholder({ slug }: { slug: string }) {
  const mod = MODULES.find((m) => m.slug === slug);
  if (!mod) return null;
  return (
    <section className="stack">
      <p className="eyebrow">Module {mod.number}</p>
      <h1>{mod.name}</h1>
      <p className="lead">{mod.summary}</p>
      <p className="muted">MVP scope: {mod.mvp}</p>
      <p className="notice">Not implemented yet. See AGENTS.md for the build plan.</p>
    </section>
  );
}
