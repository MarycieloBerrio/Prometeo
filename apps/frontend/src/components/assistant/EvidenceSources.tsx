"use client";

import { useRef, useState } from "react";

import type { RetrievedDocument } from "@prometeo/contracts";

import { Group } from "@/components/assistant/Group";
import { PdfPassage } from "@/components/assistant/PdfPassage";
import { SourceLine } from "@/components/trials/SourceLine";
import { Icon } from "@/components/ui/Icon";
import { externalUrl } from "@/domain/format";
import { quotedRanges } from "@/domain/passage-match";

const RELATION: Record<RetrievedDocument["relation"], string> = {
  same: "Same investigation as the trials",
  related: "Related investigation",
  other: "Other investigation · background",
};

function isPdf(document: RetrievedDocument): boolean {
  return document.provenance.source_file?.toLowerCase().endsWith(".pdf") ?? false;
}

/** The excerpt with the passages the interpretation quotes marked in place. */
function Excerpt({ document }: { document: RetrievedDocument }) {
  const text = document.excerpt.split(/\s+/).join(" ").trim();
  const ranges = quotedRanges(text, document.cited_passages);
  const parts: Array<{ text: string; quoted: boolean }> = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    if (start > cursor) parts.push({ text: text.slice(cursor, start), quoted: false });
    parts.push({ text: text.slice(start, end), quoted: true });
    cursor = end;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), quoted: false });
  return (
    <p className="small reader-excerpt">
      “{parts.map((part, i) => (part.quoted ? <mark key={i}>{part.text}</mark> : <span key={i}>{part.text}</span>))}”
    </p>
  );
}

/**
 * Cited sources and retrieved documents, with the source shown beside them: the PDF page with
 * the excerpt highlighted when the server holds the file, the excerpt itself otherwise.
 */
export function EvidenceSources({ sources, documents }: { sources: string[]; documents: RetrievedDocument[] }) {
  const preferred =
    documents.find((d) => d.cited_passages.length > 0 && isPdf(d)) ??
    documents.find((d) => d.cited_passages.length > 0) ??
    documents.find(isPdf) ??
    documents[0];
  const [selectedId, setSelectedId] = useState<string | null>(preferred?.id ?? null);
  const [missing, setMissing] = useState<Record<string, boolean>>({});
  const reader = useRef<HTMLDivElement>(null);
  const selected = documents.find((d) => d.id === selectedId) ?? null;

  function open(id: string) {
    setSelectedId(id);
    reader.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <>
      <Group icon="book" title="Cited sources" count={sources.length}>
        <ul className="bullets cited-sources">
          {sources.map((source, index) => {
            const document = documents.find((d) => d.provenance.reference === source);
            const href = externalUrl(source);
            return (
              <li key={`${source}-${index}`}>
                {href ? <a className="link" href={href} target="_blank" rel="noreferrer">{source}</a> : source}
                {document && (
                  <button type="button" className="source-open" onClick={() => open(document.id)}>
                    <Icon name="book" size={13} /> {isPdf(document) ? "Read in the PDF" : "Read the passage"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </Group>

      <Group icon="book" title="Documents · read the source in place" count={documents.length}>
        <div className="reader" ref={reader}>
          <ol className="reader-list">
            {documents.map((document) => {
              const current = document.id === selectedId;
              return (
                <li key={document.id} className={current ? "is-selected" : undefined}>
                  <div className="reader-tags">
                    <span className={`reader-tag relation-${document.relation}`}>{RELATION[document.relation]}</span>
                    {document.cited_passages.length > 0 && <span className="reader-tag reader-tag-quoted">Quoted by the interpretation</span>}
                  </div>
                  <Excerpt document={document} />
                  <SourceLine provenance={document.provenance} />
                  <button type="button" className="source-open" onClick={() => setSelectedId(document.id)} aria-pressed={current}>
                    <Icon name="book" size={13} /> {isPdf(document) ? "Show in the PDF" : "Show the passage"}
                  </button>
                </li>
              );
            })}
          </ol>
          <aside className="reader-pane" aria-label="Source document">
            {selected ? (
              <>
                <p className="eyebrow">SOURCE IN PLACE</p>
                <strong className="reader-title">{selected.provenance.reference}</strong>
                {isPdf(selected) && !missing[selected.id] ? (
                  <PdfPassage
                    key={selected.id}
                    source={selected}
                    onUnavailable={() => setMissing((seen) => ({ ...seen, [selected.id]: true }))}
                  />
                ) : (
                  <>
                    <p className="small muted pdf-note">
                      {isPdf(selected)
                        ? "This server holds no local copy of the PDF, so the retrieved passage is shown instead."
                        : "This source is not a PDF, so the retrieved passage is shown instead."}
                    </p>
                    <Excerpt document={selected} />
                    <SourceLine provenance={selected.provenance} />
                  </>
                )}
              </>
            ) : (
              <p className="small muted">Select a document to read its source here.</p>
            )}
          </aside>
        </div>
      </Group>
    </>
  );
}
