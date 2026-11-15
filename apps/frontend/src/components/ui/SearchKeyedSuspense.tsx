"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";

/**
 * Suspense boundary that is new for every query string.
 *
 * A plain boundary only shows its fallback the first time: when the same page is asked again
 * with other search params, React keeps the old content on screen until the new content is
 * ready, which looks like nothing is happening. Keying the boundary by the query makes each
 * question a fresh boundary, so the fallback replaces the stale result at once.
 *
 * Wrap it in an outer <Suspense>: reading search params suspends during prerender.
 */
export function SearchKeyedSuspense({
  fallback,
  when,
  children,
}: {
  fallback: ReactNode;
  /** Only show the fallback when this search param is set (e.g. no question, nothing to wait for). */
  when?: string;
  children: ReactNode;
}) {
  const params = useSearchParams();
  const waiting = !when || Boolean(params.get(when)?.trim());
  return <Suspense key={params.toString()} fallback={waiting ? fallback : null}>{children}</Suspense>;
}
