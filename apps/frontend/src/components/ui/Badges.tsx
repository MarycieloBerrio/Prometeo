import { Icon, type IconName } from "@/components/ui/Icon";

const QUALITY_LABELS: Record<string, string> = {
  measured: "Measured",
  derived: "Derived",
  extracted: "Unreviewed",
  unavailable: "Unavailable",
  synthetic: "Synthetic",
};

const QUALITY_HINTS: Record<string, string> = {
  measured: "Reported in a NASA source and checked against it",
  derived: "Computed by Prometeo from measured data",
  extracted: "Pulled automatically from a document, not yet reviewed",
  unavailable: "Known to be missing",
  synthetic: "Invented development fixture. Not NASA data",
};

/** Data quality must always be visible next to a value (AGENTS.md § Scientific integrity). */
export function DataQualityBadge({ quality }: { quality: string }) {
  return (
    <span className={`badge badge-${quality}`} title={QUALITY_HINTS[quality] ?? quality}>
      {QUALITY_LABELS[quality] ?? quality}
    </span>
  );
}

const TIERS: Record<string, { label: string; icon: IconName; tone: string }> = {
  direct: { label: "Direct evidence", icon: "check", tone: "ok" },
  partial: { label: "Partial evidence", icon: "alert", tone: "warn" },
  insufficient: { label: "Insufficient evidence", icon: "ban", tone: "danger" },
};

/** EvidenceRank tier. Interpretable levels only, never a percentage. */
export function TierBadge({ tier }: { tier: string }) {
  const t = TIERS[tier] ?? { label: tier, icon: "info" as const, tone: "neutral" };
  return (
    <span className={`pill tone-${t.tone}`}>
      <Icon name={t.icon} size={14} />
      {t.label}
    </span>
  );
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="tag">{children}</span>;
}
