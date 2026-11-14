import Form from "next/form";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";

const STARTERS = [
  "How does airflow change flame spread in microgravity?",
  "Which trials measured extinction?",
];

export default function Home() {
  return (
    <div className="ignition-home">
      <div className="ignition-scene" aria-hidden="true">
        <div className="ignition-light" />
        <div className="ignition-poster" />
        <video
          className="ignition-video"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          poster="/visuals/hero-fire-poster.webp"
        >
          <source src="/visuals/hero-fire.mp4" type="video/mp4" />
        </video>
      </div>

      <header className="ignition-header">
        <Link href="/" className="ignition-brand" aria-label="Prometeo home">
          PROMETEO<span className="ignition-brand-dot">.</span>
        </Link>
        <nav className="ignition-nav" aria-label="Main navigation">
          <Link href="/explorer">Explore trials</Link>
          <Link href="/compare">Compare</Link>
          <Link href="/flamevision">Watch</Link>
        </nav>
      </header>

      <section className="ignition-content" aria-labelledby="ignition-title">
        <p className="ignition-kicker"><span /> MICROGRAVITY COMBUSTION / EVIDENCE WORKSPACE</p>
        <h1 id="ignition-title">Follow the evidence<br /><em>through the flame.</em></h1>
        <p className="ignition-intro">
          Investigate NASA combustion experiments through recorded trials,
          source video and answers grounded in what was actually observed.
        </p>
        <Form action="/assistant" className="ignition-search" role="search">
          <label htmlFor="ignition-query">Ask the evidence</label>
          <div className="ignition-search-row">
            <Icon name="search" size={22} />
            <input
              id="ignition-query"
              name="q"
              type="search"
              placeholder="What do you want to investigate?"
              autoComplete="off"
              required
            />
            <button type="submit" aria-label="Search evidence">
              <span>Search</span><Icon name="arrowRight" size={19} />
            </button>
          </div>
        </Form>
        <div className="ignition-starters" aria-label="Example questions">
          <span>Try asking</span>
          {STARTERS.map((question) => (
            <Link key={question} href={{ pathname: "/assistant", query: { q: question } }}>
              {question}<Icon name="arrowRight" size={14} />
            </Link>
          ))}
        </div>
      </section>

      <footer className="ignition-footer">
        <span>NASA SPACE APPS / PROMETEO</span>
        <span>Atmospheric footage · not experimental video</span>
        <Link href="/explorer">Enter experiment explorer <Icon name="arrowRight" size={14} /></Link>
      </footer>
    </div>
  );
}
