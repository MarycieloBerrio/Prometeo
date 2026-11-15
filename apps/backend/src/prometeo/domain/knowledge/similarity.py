"""Near-duplicate detection for retrieved text chunks.

NASA reports repeat boilerplate: the same paragraph appears on several pages of one report
and again in the interim reports of the same investigation. Returned side by side, those
copies crowd distinct sources out of a short result list without adding information.

Two texts are near-duplicates when the smaller one's word 3-grams are almost all contained
in the other. This is a lexical test only: it says the wording repeats, never that two
experiments agree.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")
_SHINGLE = 3

# Share of the smaller text's 3-grams found in the other. On the PSI knowledge base, repeated
# boilerplate scores >= 0.83 and adjacent chunks that only share their overlap sentences
# score <= 0.70, so 0.8 separates the two.
NEAR_DUPLICATE_CONTAINMENT = 0.8


def _shingles(text: str) -> frozenset[tuple[str, ...]]:
    words = _WORD.findall(text.lower())
    if len(words) < _SHINGLE:
        return frozenset({tuple(words)}) if words else frozenset()
    return frozenset(tuple(words[i : i + _SHINGLE]) for i in range(len(words) - _SHINGLE + 1))


def is_near_duplicate(a: str, b: str, threshold: float = NEAR_DUPLICATE_CONTAINMENT) -> bool:
    """True when `a` and `b` repeat (almost) the same wording."""
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return sa == sb
    return len(sa & sb) / min(len(sa), len(sb)) >= threshold
