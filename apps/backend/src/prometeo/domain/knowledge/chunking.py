"""Deterministic text chunking for retrieval.

Chunks keep whole sentences where possible and never change the words: a chunk is always a
verbatim slice of the source (whitespace aside), so a citation can be checked against the page.
"""

from __future__ import annotations

import re

_PARAGRAPH = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")

DEFAULT_MAX_CHARS = 1200  # ~300 tokens: fits the 512-token window of bge-small-en-v1.5
DEFAULT_OVERLAP_CHARS = 150


def chunk_text(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[str]:
    """Split `text` into chunks of at most `max_chars`, overlapping by whole sentences.

    Paragraphs are packed together until the limit; a chunk starts with the trailing sentences
    of the previous one (up to `overlap_chars`) so a statement cut at a boundary stays findable.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if not 0 <= overlap_chars < max_chars:
        raise ValueError("overlap_chars must be >= 0 and smaller than max_chars")

    units = _units(text, max_chars)
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for unit in units:
        added = len(unit) + (1 if current else 0)
        if current and size + added > max_chars:
            chunks.append(" ".join(current))
            current = _overlap_tail(current, overlap_chars, max_chars - len(unit) - 1)
            size = len(" ".join(current))
            added = len(unit) + (1 if current else 0)
        current.append(unit)
        size += added
    if current:
        chunks.append(" ".join(current))
    return chunks


def _units(text: str, max_chars: int) -> list[str]:
    """Sentences in reading order, with whitespace collapsed; overlong ones are hard-split."""
    units: list[str] = []
    for paragraph in _PARAGRAPH.split(text):
        cleaned = _WHITESPACE.sub(" ", paragraph).strip()
        if not cleaned:
            continue
        for sentence in _SENTENCE_END.split(cleaned):
            sentence = sentence.strip()
            while len(sentence) > max_chars:
                cut = sentence.rfind(" ", 0, max_chars)
                cut = cut if cut > 0 else max_chars
                units.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if sentence:
                units.append(sentence)
    return units


def _overlap_tail(previous: list[str], overlap_chars: int, room: int) -> list[str]:
    """Trailing sentences of the previous chunk that fit both the overlap and the next chunk."""
    budget = min(overlap_chars, room)
    tail: list[str] = []
    used = 0
    for sentence in reversed(previous):
        cost = len(sentence) + (1 if tail else 0)
        if used + cost > budget:
            break
        tail.insert(0, sentence)
        used += cost
    return tail
