import Link from "next/link";

import { Callout, EmptyState } from "@/components/ui/Callout";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, Section } from "@/components/ui/PageHeader";
import { Steps, type Step } from "@/components/ui/Steps";

const METHOD: Step[] = [
  { icon: "video", title: "NASA video", note: "original footage" },
  { icon: "flame", title: "Track the edge", note: "frame by frame" },
  { icon: "chart", title: "Position vs time", note: "slope = spread rate" },
  { icon: "check", title: "Validate", note: "against a published value" },
];

export default function FlameVisionPage() {
  return (
    <div className="page">
      <PageHeader slug="flamevision" />

      <Steps steps={METHOD} />

      <EmptyState
        icon="video"
        title="No processed video yet"
        action={
          <Link href="/explorer" className="btn">
            <Icon name="search" size={16} />
            Browse trials
          </Link>
        }
      >
        The first tracked BASS-II video will appear here with its overlay and position–time plot.
      </EmptyState>

      <Section title="What the track means">
        <div className="principles">
          <div className="principle">
            <Icon name="flame" size={20} />
            <div>
              <strong>Luminous leading edge</strong>
              <p className="muted small">The visible front. Not the reaction front or the hottest zone.</p>
            </div>
          </div>
          <div className="principle">
            <Icon name="sigma" size={20} />
            <div>
              <strong>Derived, with a method</strong>
              <p className="muted small">Spread rate is computed from the track and labelled “Derived”.</p>
            </div>
          </div>
          <div className="principle">
            <Icon name="alert" size={20} />
            <div>
              <strong>Unvalidated by default</strong>
              <p className="muted small">A track counts only after it matches a reference value.</p>
            </div>
          </div>
        </div>
      </Section>

      <Callout tone="info" title="Why no demo curve?">
        Prometeo never shows invented measurements. The plot appears when a real video has been processed.
      </Callout>
    </div>
  );
}
