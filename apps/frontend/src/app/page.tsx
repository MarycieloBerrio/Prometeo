import Link from "next/link";

import { Icon, type IconName } from "@/components/ui/Icon";
import { MODULES } from "@/domain/modules";

const PRINCIPLES: { icon: IconName; title: string; note: string }[] = [
  { icon: "book", title: "Every value has a source", note: "Unit, provenance and data quality." },
  { icon: "ban", title: "No extrapolation", note: "No data means no answer." },
  { icon: "alert", title: "Limits are visible", note: "Uncertainty is part of the result." },
];

export default function Home() {
  const flow = MODULES.filter((m) => ["explorer", "compare", "assistant"].includes(m.slug));
  return (
    <div className="page">
      <section className="hero">
        <p className="eyebrow">NASA Space Apps 2026 · Flame in Freefall</p>
        <h1>What do we really know about fire in space?</h1>
        <p className="lead">
          Prometeo helps you find documented microgravity combustion trials, check physical comparability, and trace a supported explanation to its sources.
        </p>
        <p className="small muted">Research support, not safety certification. Empty evidence is never a safety finding.</p>
        <div className="row">
          <Link href="/explorer" className="btn btn-primary btn-large">
            Start exploring
            <Icon name="arrowRight" size={18} />
          </Link>
          <Link href="/assistant" className="btn btn-large">
            <Icon name="chat" size={18} />
            Ask a question
          </Link>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2>How it works</h2>
          <span className="muted small">Three core modules · one traceable conclusion</span>
        </div>
        <div className="flow">
          {flow.map((m) => (
              <Link key={m.slug} href={`/${m.slug}`} className="card flow-card">
                <span className="flow-top">
                  <span className="page-icon">
                    <Icon name={m.icon} size={22} />
                  </span>
                  <span className="flow-number">{Number(m.number)}</span>
                </span>
                <h3>{m.label}</h3>
                <p className="muted small">{m.purpose}</p>
              </Link>
          ))}
        </div>
        <p className="small muted">Optional: <Link href="/flamevision" className="link">FlameVision</Link> displays a source-linked video only when a trial record provides one.</p>
      </section>

      <section className="principles">
        {PRINCIPLES.map((p) => (
          <div key={p.title} className="principle">
            <Icon name={p.icon} size={20} />
            <div>
              <strong>{p.title}</strong>
              <p className="muted small">{p.note}</p>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
