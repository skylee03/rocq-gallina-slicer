#!/usr/bin/env python3
"""End-to-end evaluation for the MetaRocq/Gallina slicer."""

from __future__ import annotations

import sys
from pathlib import Path

from gallina_slicer.meta_trace import collect_meta_trace
from gallina_slicer.slicer import (
    SlicerError,
    check_text,
    exact_slice,
    line_count,
    parse_signature,
    reduction,
    render,
    type_slice,
)

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
CASES = [
    "nat.v",
    "list.v",
    "bool.v",
    "inductive.v",
    "record.v",
    "fixpoint.v",
    "scope.v",
    "unused.v",
]


def main() -> int:
    print(f"{'file':18} {'mode':6} {'lines':>12} {'red.':>7}  check")
    print("-" * 58)
    reductions = {"exact": [], "type": []}
    failures = 0
    for filename in CASES:
        source = (CORPUS / filename).read_text(encoding="utf-8")
        sig = parse_signature(source)
        try:
            trace = collect_meta_trace(source, "target")
        except SlicerError as exc:
            print(f"{filename}: {exc}", file=sys.stderr)
            return 2
        for mode, closure in (("exact", exact_slice), ("type", type_slice)):
            keep = closure(sig, trace, "target")
            sliced = render(
                sig, keep, admit_target="target" if mode == "type" else None
            )
            before, after = line_count(source), line_count(sliced)
            pct = reduction(before, after)
            reductions[mode].append(pct)
            result = check_text(sliced)
            if not result.ok:
                failures += 1
                print(result.output, file=sys.stderr)
            print(
                f"{filename:18} {mode:6} {before:>5} -> {after:<3} "
                f"{pct:>6.1f}%  {'OK' if result.ok else 'FAIL'}"
            )
    print("-" * 58)
    for mode, values in reductions.items():
        print(
            f"{mode:6} mean reduction: {sum(values) / len(values):.1f}% "
            f"(range {min(values):.1f}%..{max(values):.1f}%)"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
