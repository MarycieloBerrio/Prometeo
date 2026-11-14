#!/usr/bin/env python3
"""Export validated staging trials to curated JSON with stable ordering.

Refuses to overwrite an existing curated file unless --force is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from validate_staging import validate_trials  # noqa: E402

# Stable key order for human diffs (unknown keys appended alphabetically).
_TRIAL_KEY_ORDER = [
    "id",
    "investigation",
    "sample_id",
    "fuel",
    "geometry",
    "oxygen",
    "ventilation",
    "pressure",
    "phenomena",
    "provenance",
    "results",
    "media",
    "notes",
    "tags",
]


def _ordered(obj: Any, key_order: list[str] | None = None) -> Any:
    if isinstance(obj, list):
        return [_ordered(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    keys = list(obj.keys())
    if key_order:
        ordered_keys = [k for k in key_order if k in obj]
        ordered_keys.extend(sorted(k for k in keys if k not in key_order))
    else:
        ordered_keys = sorted(keys)
    return {k: _ordered(obj[k]) for k in ordered_keys}


def export(staging: Path, output: Path, *, force: bool) -> int:
    records = json.loads(staging.read_text(encoding="utf-8"))
    errors = validate_trials(records, allow_synthetic=False)
    if errors:
        print(f"FAIL: staging invalid ({len(errors)} issue(s))", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if output.exists() and not force:
        print(
            f"REFUSED: {output} exists. Re-run with --force after confirming overwrite.",
            file=sys.stderr,
        )
        return 3

    curated = [_ordered(r, _TRIAL_KEY_ORDER) for r in records]
    curated.sort(key=lambda r: str(r.get("id", "")))
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(curated, indent=2, ensure_ascii=False) + "\n"
    output.write_text(text, encoding="utf-8", newline="\n")
    print(f"OK: wrote {len(curated)} trial(s) -> {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing curated file",
    )
    args = parser.parse_args(argv)
    return export(args.staging, args.output, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
