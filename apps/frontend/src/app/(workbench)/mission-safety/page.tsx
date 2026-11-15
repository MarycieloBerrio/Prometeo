import Link from "next/link";

import { Callout, EmptyState } from "@/components/ui/Callout";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";

export default function MissionSafetyPage() {
  return (
    <div className="page">
      <PageHeader slug="mission-safety" />

      <EmptyState
        icon="rocket"
        title="Planned after the MVP"
        action={
          <Link href="/compare" className="btn">
            <Icon name="grid" size={16} />
            See the coverage map
          </Link>
        }
      >
        Pick a mission scenario and see which experiments apply, and where no evidence exists.
      </EmptyState>

      <Callout tone="warn" title="Not a risk predictor">
        Microgravity results do not transfer directly to the Moon or Mars. Prometeo does not certify materials.
      </Callout>
    </div>
  );
}
