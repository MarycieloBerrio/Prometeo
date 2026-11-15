/**
 * Locates a quoted passage inside the text items of a PDF page.
 *
 * The passage was extracted from the PDF by another tool, so spacing, line breaks, hyphens and
 * ligatures differ from what the viewer reads. Both sides are therefore reduced to a stream of
 * lowercase letters and digits before matching, and each stream character remembers which text
 * item it came from and how far along that item it sits.
 *
 * Matching is lexical and all-or-nothing per piece: a piece that is not found is simply not
 * highlighted. Nothing is ever highlighted that is not in the passage.
 */

export interface TextItem {
  str: string;
}

/** A stretch of one text item, as fractions of its width (0 = start, 1 = end). */
export interface ItemSpan {
  item: number;
  from: number;
  to: number;
}

export interface PassageMatch {
  spans: ItemSpan[];
  /** Share of the passage's letters and digits that were found on the page, 0..1. */
  coverage: number;
}

interface PageIndex {
  stream: string;
  /** For each stream character: the item it belongs to. */
  owner: Int32Array;
  /** For each stream character: its position inside the item's own characters. */
  position: Int32Array;
  /** Per item: how many stream characters it contributed. */
  sizes: number[];
}

const KEEP = /[a-z0-9]/;
const MIN_PIECE = 12; // shorter fragments match by accident ("the flame", "of the")

function letters(text: string): string {
  let out = "";
  // NFKD splits ligatures ("ﬁ" -> "fi") and accents, so both sides spell words the same way.
  for (const ch of text.normalize("NFKD").toLowerCase()) if (KEEP.test(ch)) out += ch;
  return out;
}

export function indexPage(items: readonly TextItem[]): PageIndex {
  const parts: string[] = [];
  const owner: number[] = [];
  const position: number[] = [];
  const sizes: number[] = [];
  items.forEach((item, index) => {
    const own = letters(item.str);
    sizes.push(own.length);
    parts.push(own);
    for (let i = 0; i < own.length; i += 1) {
      owner.push(index);
      position.push(i);
    }
  });
  return { stream: parts.join(""), owner: Int32Array.from(owner), position: Int32Array.from(position), sizes };
}

function pieces(passage: string): string[] {
  // Sentences first: the page may order blocks (columns, captions, footers) differently, so a
  // long passage rarely survives as one run but its sentences do.
  return passage
    .split(/(?<=[.!?;:])\s+/)
    .map(letters)
    .filter((piece) => piece.length >= MIN_PIECE);
}

function spansOf(index: PageIndex, start: number, end: number): ItemSpan[] {
  const spans: ItemSpan[] = [];
  let i = start;
  while (i < end) {
    const item = index.owner[i];
    let j = i;
    while (j + 1 < end && index.owner[j + 1] === item) j += 1;
    const size = index.sizes[item] || 1;
    spans.push({ item, from: index.position[i] / size, to: (index.position[j] + 1) / size });
    i = j + 1;
  }
  return spans;
}

export function locatePassage(index: PageIndex, passage: string): PassageMatch {
  const whole = letters(passage);
  if (whole.length < MIN_PIECE) return { spans: [], coverage: 0 };

  const at = index.stream.indexOf(whole);
  if (at >= 0) return { spans: spansOf(index, at, at + whole.length), coverage: 1 };

  const spans: ItemSpan[] = [];
  let found = 0;
  for (const piece of pieces(passage)) {
    const start = index.stream.indexOf(piece);
    if (start < 0) continue;
    found += piece.length;
    spans.push(...spansOf(index, start, start + piece.length));
  }
  return { spans, coverage: Math.min(1, found / whole.length) };
}

/** Ranges of `text` (after collapsing whitespace) that quote one of `passages`. */
export function quotedRanges(text: string, passages: readonly string[]): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  for (const passage of passages) {
    const quoted = passage.split(/\s+/).join(" ").trim();
    const start = quoted ? text.indexOf(quoted) : -1;
    if (start >= 0) ranges.push([start, start + quoted.length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: Array<[number, number]> = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else merged.push([range[0], range[1]]);
  }
  return merged;
}
