"use client";

import { useLinkStatus } from "next/link";
import { useFormStatus } from "react-dom";

import { ASK_WAIT_LABEL } from "@/components/assistant/labels";
import { Icon } from "@/components/ui/Icon";
import { LoadingState } from "@/components/ui/LoadingState";

/** Submit button that says so while the question is being answered. Must sit inside the form. */
export function AskSubmit() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="btn btn-primary" disabled={pending} aria-busy={pending}>
      {pending ? "Examining…" : "Examine evidence"}
      <Icon name="arrowRight" size={16} />
    </button>
  );
}

/** Progress line under the question while the form's navigation is pending. */
export function AskPendingNotice() {
  const { pending } = useFormStatus();
  return pending ? <LoadingState label={ASK_WAIT_LABEL} /> : null;
}

/** Inline marker for a suggested question that was clicked. Must sit inside its <Link>. */
export function LinkPendingMark() {
  const { pending } = useLinkStatus();
  return pending ? <span className="link-pending" role="status">Asking…</span> : null;
}
