export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="loading-pulse" aria-hidden="true" />
      <span className="eyebrow">{label}</span>
      <span className="loading-track" aria-hidden="true"><i /></span>
    </div>
  );
}
