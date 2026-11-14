import Link from "next/link";

import { MODULES } from "@/domain/modules";

export default function Home() {
  return (
    <section className="stack">
      <p className="eyebrow">NASA Space Apps 2026 · Flame in Freefall</p>
      <h1>From microgravity fire data to scientific evidence</h1>
      <p className="lead">
        Prometeo connects NASA combustion experiments, measurements and video into answers that state
        what is known, under which conditions, with what evidence and where the limits are.
      </p>
      <div className="grid">
        {MODULES.map((m) => (
          <Link key={m.slug} href={`/${m.slug}`} className="card">
            <span className="eyebrow">{m.number}</span>
            <h2>{m.name}</h2>
            <p>{m.summary}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
