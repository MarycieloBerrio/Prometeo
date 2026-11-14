import type { ReactNode } from "react";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { MODULES, moduleBySlug } from "@/domain/modules";

const FLOW = MODULES.filter((module) => module.inFlow);
const ACTIONS: Record<string, string> = {
  explorer: "Build a comparison",
  compare: "Inspect flame media",
  flamevision: "Ask the evidence",
  assistant: "Browse experiments",
};

/** The same research route and editorial heading on every working page. */
export function PageHeader({ slug, children }: { slug: string; children?: ReactNode }) {
  const mod = moduleBySlug(slug);
  const index = FLOW.findIndex((item) => item.slug === slug);
  const next = FLOW[(index + 1) % FLOW.length];
  return (
    <header className="research-header">
      <div className="research-route">
        <span>RESEARCH PATH <strong>{index < 0 ? "FUTURE" : `${mod.number} / 04`}</strong></span>
        <div className="research-route-lines" aria-hidden="true">
          {FLOW.map((item) => <i key={item.slug} className={item.slug === slug ? "is-current" : ""} />)}
        </div>
        <Link href={`/${next.slug}`}>{ACTIONS[slug] ?? "Browse experiments"} <Icon name="arrowRight" size={15} /></Link>
      </div>
      <div className="research-heading">
        <h1>{mod.name}</h1>
        <p>{mod.purpose}</p>
      </div>
      {children && <div className="page-actions">{children}</div>}
    </header>
  );
}

export function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-head">
        <span className="section-marker" aria-hidden="true" />
        <h2>{title}</h2>
        {hint && <span className="muted small">{hint}</span>}
      </div>
      {children}
    </section>
  );
}
