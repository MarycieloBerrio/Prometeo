const LABELS: Record<string, string> = {
  measured: "Measured",
  derived: "Derived",
  extracted: "Extracted · unreviewed",
  unavailable: "Unavailable",
  synthetic: "Synthetic · not NASA data",
};

/** Data quality must always be visible next to a value (AGENTS.md § Scientific integrity). */
export function DataQualityBadge({ quality }: { quality: string }) {
  return (
    <span className={`badge badge-${quality}`} title={`Data quality: ${quality}`}>
      {LABELS[quality] ?? quality}
    </span>
  );
}
