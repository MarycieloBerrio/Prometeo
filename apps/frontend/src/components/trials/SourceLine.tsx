import type { Provenance } from "@prometeo/contracts";

import { Icon } from "@/components/ui/Icon";
import { externalUrl } from "@/domain/format";

/** Where a value comes from. Shown wherever a value or excerpt is shown. */
export function SourceLine({ provenance }: { provenance: Provenance }) {
  const href = externalUrl(provenance.doi ? `https://doi.org/${provenance.doi}` : provenance.url);
  return (
    <span className="source small">
      <Icon name="book" size={14} label="Source" />
      <span>
        {provenance.reference}
        {provenance.page && <span className="muted"> · {provenance.page}</span>}
      </span>
      {href && (
        <a href={href} target="_blank" rel="noreferrer" aria-label="Open source">
          <Icon name="external" size={14} />
        </a>
      )}
    </span>
  );
}
