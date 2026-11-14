import type { ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import { moduleBySlug } from "@/domain/modules";

/** Same header on every module page: icon, step number, name, one-line purpose. */
export function PageHeader({ slug, children }: { slug: string; children?: ReactNode }) {
  const mod = moduleBySlug(slug);
  return (
    <header className="page-header">
      <span className="page-icon">
        <Icon name={mod.icon} size={24} />
      </span>
      <div>
        <p className="eyebrow">Step {mod.number}</p>
        <h1>{mod.name}</h1>
        <p className="muted">{mod.purpose}</p>
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
        <h2>{title}</h2>
        {hint && <span className="muted small">{hint}</span>}
      </div>
      {children}
    </section>
  );
}
