"use client";

import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";

import type { RetrievedDocument } from "@prometeo/contracts";

import { Icon } from "@/components/ui/Icon";
import { LoadingState } from "@/components/ui/LoadingState";
import { indexPage, locatePassage, type ItemSpan } from "@/domain/passage-match";

type Status = "loading" | "ready" | "unavailable" | "error";

/** A highlight rectangle, as fractions of the rendered page. */
interface Mark {
  left: number;
  top: number;
  width: number;
  height: number;
  strong: boolean;
}

interface PositionedText {
  str: string;
  transform: number[];
  width: number;
  height: number;
}

const RENDER_SCALE = 1.7; // sharp at the pane's width without rendering a huge bitmap
const LOCATED = 0.6; // share of the excerpt that must be found to call a page "the page"
const SEARCH_WITHOUT_PAGE = 80; // pages scanned when the record carries no page number
const RANGE_CHUNK = 256 * 1024; // bytes per request; a report can be tens of megabytes

export function fileUrl(chunkId: string): string {
  return `/api/documents/${encodeURIComponent(chunkId)}/file`;
}

async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
  return pdfjs;
}

async function pageText(pdf: PDFDocumentProxy, pageNumber: number): Promise<PositionedText[]> {
  const page = await pdf.getPage(pageNumber);
  const content = await page.getTextContent();
  return content.items.filter((item): item is typeof item & PositionedText => "str" in item && "transform" in item);
}

/** The page that holds the excerpt: the recorded page, its neighbours, or a bounded scan. */
async function findPage(pdf: PDFDocumentProxy, recorded: string | null | undefined, excerpt: string) {
  const wanted = Number.parseInt(recorded ?? "", 10);
  const known = Number.isInteger(wanted) && wanted >= 1 && wanted <= pdf.numPages;
  const order = known
    ? [wanted, wanted + 1, wanted - 1, wanted + 2, wanted - 2].filter((n) => n >= 1 && n <= pdf.numPages)
    : Array.from({ length: Math.min(pdf.numPages, SEARCH_WITHOUT_PAGE) }, (_, i) => i + 1);
  let best = { page: known ? wanted : 1, coverage: 0 };
  for (const candidate of order) {
    const coverage = locatePassage(indexPage(await pageText(pdf, candidate)), excerpt).coverage;
    if (coverage > best.coverage) best = { page: candidate, coverage };
    if (coverage >= LOCATED) break;
  }
  return best;
}

/**
 * The source PDF, on the page of a retrieved excerpt, with the excerpt and the passages the
 * interpretation quotes drawn over the page. Falls back to nothing (the caller shows the text)
 * when the server holds no local copy of the file.
 */
export function PdfPassage({ source, onUnavailable }: { source: RetrievedDocument; onUnavailable: () => void }) {
  const [status, setStatus] = useState<Status>("loading");
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [home, setHome] = useState<{ page: number; coverage: number }>({ page: 1, coverage: 0 });
  const [page, setPage] = useState(1);
  const [marks, setMarks] = useState<Mark[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const unavailable = useRef(onUnavailable);
  useEffect(() => {
    unavailable.current = onUnavailable;
  }, [onUnavailable]);

  const { id, excerpt, cited_passages: quoted } = source;
  const recordedPage = source.provenance.page;

  useEffect(() => {
    let cancelled = false;
    let loading: PDFDocumentLoadingTask | null = null;
    (async () => {
      // One byte tells whether the server holds the file, and how long it is, without
      // downloading it.
      const url = fileUrl(id);
      const probe = await fetch(url, { headers: { Range: "bytes=0-0" } });
      void probe.body?.cancel();
      if (probe.status === 404) {
        if (!cancelled) {
          setStatus("unavailable");
          unavailable.current();
        }
        return;
      }
      if (!probe.ok) throw new Error(`source file: HTTP ${probe.status}`);
      const length = Number(probe.headers.get("content-range")?.split("/")[1]);
      const pdfjs = await loadPdfjs();
      if (probe.status === 206 && Number.isFinite(length) && length > 0) {
        // Reports run to tens of megabytes and one page needs a small part of the file, so
        // the viewer asks for byte ranges itself, on demand.
        class RangeLoader extends pdfjs.PDFDataRangeTransport {
          requestDataRange(begin: number, end: number) {
            fetch(url, { headers: { Range: `bytes=${begin}-${end - 1}` } })
              .then((part) => {
                if (!part.ok) throw new Error(`source file range: HTTP ${part.status}`);
                return part.arrayBuffer();
              })
              .then((bytes) => this.onDataRange(begin, new Uint8Array(bytes)))
              .catch(() => {
                if (!cancelled) setStatus("error");
              });
          }
        }
        loading = pdfjs.getDocument({
          range: new RangeLoader(length, null),
          rangeChunkSize: RANGE_CHUNK,
          disableAutoFetch: true,
          disableStream: true,
        });
      } else {
        loading = pdfjs.getDocument({ url }); // no range support: load the whole file
      }
      const document = await loading.promise;
      if (cancelled) return;
      const start = await findPage(document, recordedPage, excerpt);
      if (cancelled) return;
      setPdf(document);
      setHome(start);
      setPage(start.page);
      setStatus("ready");
    })().catch(() => {
      if (!cancelled) setStatus("error");
    });
    return () => {
      cancelled = true;
      void loading?.destroy(); // also releases the worker's copy of the file
    };
  }, [id, excerpt, recordedPage]);

  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    let task: RenderTask | null = null;
    (async () => {
      const pdfPage = await pdf.getPage(page);
      const viewport = pdfPage.getViewport({ scale: RENDER_SCALE });
      const canvas = canvasRef.current;
      if (!canvas || cancelled) return;
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      task = pdfPage.render({ canvas, viewport });
      await task.promise;
      const items = await pageText(pdf, page);
      if (cancelled) return;
      const index = indexPage(items);
      const rects = (spans: ItemSpan[], strong: boolean): Mark[] =>
        spans.flatMap((span) => {
          const item = items[span.item];
          const [a, b, , d, x, y] = item.transform;
          if (Math.abs(b) > 1e-3 || a <= 0) return []; // rotated text: leave it unmarked
          const height = item.height || Math.abs(d);
          // PDF space has its origin at the bottom left; (x, y) is the start of the baseline.
          const [x0, y0] = viewport.convertToViewportPoint(x + item.width * span.from, y - height * 0.24);
          const [x1, y1] = viewport.convertToViewportPoint(x + item.width * span.to, y + height * 0.84);
          return [{
            left: Math.min(x0, x1) / viewport.width,
            top: Math.min(y0, y1) / viewport.height,
            width: Math.abs(x1 - x0) / viewport.width,
            height: Math.abs(y1 - y0) / viewport.height,
            strong,
          }];
        });
      setMarks([
        ...rects(locatePassage(index, excerpt).spans, false),
        ...quoted.flatMap((passage) => rects(locatePassage(index, passage).spans, true)),
      ]);
    })().catch(() => {
      // A cancelled render rejects; the next effect run draws the page that replaced it.
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [pdf, page, excerpt, quoted]);

  // Bring the passage into view inside the pane (never scroll the whole page).
  useEffect(() => {
    const pane = scrollRef.current;
    const first = marks.find((mark) => mark.strong) ?? marks[0];
    if (!pane || !first) return;
    pane.scrollTop = Math.max(0, first.top * pane.scrollHeight - pane.clientHeight / 3);
  }, [marks]);

  if (status === "unavailable" || status === "error") {
    return status === "error" ? (
      <p className="small muted pdf-note">The source document could not be opened here.</p>
    ) : null;
  }

  const pages = pdf?.numPages ?? 0;
  const located = home.coverage >= LOCATED;
  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <div className="pdf-nav">
          <button type="button" onClick={() => setPage((n) => Math.max(1, n - 1))} disabled={!pdf || page <= 1} aria-label="Previous page">
            <Icon name="arrowLeft" size={15} />
          </button>
          <span className="mono small">{pdf ? `Page ${page} of ${pages}` : "Opening…"}</span>
          <button type="button" onClick={() => setPage((n) => Math.min(pages, n + 1))} disabled={!pdf || page >= pages} aria-label="Next page">
            <Icon name="arrowRight" size={15} />
          </button>
          {pdf && page !== home.page && (
            <button type="button" className="pdf-return" onClick={() => setPage(home.page)}>
              Back to the passage
            </button>
          )}
        </div>
        <a className="link small" href={`${fileUrl(id)}#page=${page}`} target="_blank" rel="noreferrer">
          Open the full PDF <Icon name="external" size={13} />
        </a>
      </div>
      {status === "loading" && <LoadingState label="Opening the source document" />}
      <div className="pdf-scroll" ref={scrollRef} hidden={status !== "ready"}>
        <div className="pdf-stage">
          <canvas ref={canvasRef} aria-label={`Page ${page} of ${source.provenance.reference}`} />
          {marks.map((mark, i) => (
            <span
              key={i}
              className={`pdf-mark${mark.strong ? " pdf-mark-strong" : ""}`}
              style={{
                left: `${mark.left * 100}%`,
                top: `${mark.top * 100}%`,
                width: `${mark.width * 100}%`,
                height: `${mark.height * 100}%`,
              }}
            />
          ))}
        </div>
      </div>
      {status === "ready" && (
        <p className="small muted pdf-legend">
          <span><i className="pdf-key" /> Retrieved excerpt</span>
          <span><i className="pdf-key pdf-key-strong" /> Quoted by the interpretation</span>
          {!located && page === home.page && (
            <span>The excerpt could not be located on this page; it is shown as recorded.</span>
          )}
        </p>
      )}
    </div>
  );
}
