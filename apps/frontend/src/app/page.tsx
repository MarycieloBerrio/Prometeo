import Link from "next/link";

import { Icon, type IconName } from "@/components/ui/Icon";
import { ThermalField } from "@/components/ui/ThermalField";

const PATH: { number: string; icon: IconName; title: string; description: string; href: string }[] = [
  {
    number: "01",
    icon: "search",
    title: "Find an experiment",
    description: "Browse material, oxygen, airflow and source together.",
    href: "/explorer",
  },
  {
    number: "02",
    icon: "compare",
    title: "Test the comparison",
    description: "Isolate what changed. Let the Physics Validator check the rest.",
    href: "/compare",
  },
  {
    number: "03",
    icon: "chat",
    title: "Trace the conclusion",
    description: "Read an answer, a cited limitation, or an honest refusal.",
    href: "/assistant",
  },
];

export default function Home() {
  return (
    <div className="page home-page">
      <section className="home-hero">
        <div className="hero-content">
          <p className="eyebrow hero-eyebrow"><span className="eyebrow-line" /> THE SCIENCE OF FIRE IN FREEFALL</p>
          <h1>Follow the <em>evidence</em> through the flame.</h1>
          <p className="lead">
            Microgravity changes how fire grows. Prometeo turns scattered combustion trials into an explorable
            record of conditions, physical comparisons and traceable conclusions.
          </p>
          <div className="hero-actions">
            <Link href="/explorer" className="btn btn-primary btn-large">Enter the Explorer <Icon name="arrowRight" size={18} /></Link>
            <Link href="/compare" className="btn btn-large">Open Comparison Lab <Icon name="compare" size={17} /></Link>
          </div>
          <div className="hero-quicklinks" aria-label="Other instruments">
            <Link href="/assistant"><Icon name="chat" size={15} /> Ask the evidence</Link>
            <Link href="/flamevision"><Icon name="video" size={15} /> Inspect FlameVision</Link>
          </div>
          <p className="hero-disclaimer"><Icon name="shield" size={15} /> Research support. No safety certification or prediction beyond recorded evidence.</p>
        </div>
        <div className="hero-visual">
          <ThermalField hero />
          <span className="hero-visual-note">ABSTRACT THERMAL FIELD · NOT EXPERIMENTAL DATA</span>
        </div>
      </section>

      <section className="home-path" aria-labelledby="path-title">
        <div className="home-path-heading">
          <p className="eyebrow">A TRACEABLE RESEARCH PATH</p>
          <h2 id="path-title">From question to qualified finding.</h2>
          <p>Three connected instruments keep the source and the limits in view.</p>
        </div>
        <div className="path-rail">
          {PATH.map((item) => (
            <Link href={item.href} className="path-stop" key={item.number}>
              <span className="path-number">{item.number}<span className="path-dot" /></span>
              <span className="path-symbol"><Icon name={item.icon} size={22} /></span>
              <strong>{item.title}</strong>
              <span className="muted small">{item.description}</span>
              <span className="path-action">OPEN INSTRUMENT <Icon name="arrowRight" size={14} /></span>
            </Link>
          ))}
        </div>
      </section>

      <section className="evidence-manifesto" aria-label="Scientific guardrails">
        <div><span>01 / PROVENANCE</span><strong>Every value has a trail.</strong><p>Source, unit and quality travel with the measurement.</p></div>
        <div><span>02 / PHYSICS</span><strong>Compatibility comes first.</strong><p>A difference appears only when the conditions support it.</p></div>
        <div><span>03 / UNCERTAINTY</span><strong>A gap is still a finding.</strong><p>No recorded evidence is never presented as safety.</p></div>
      </section>
    </div>
  );
}
