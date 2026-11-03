from __future__ import annotations

import unittest
from pathlib import Path

from gallina_slicer.meta_trace import collect_meta_trace
from gallina_slicer.slicer import (
    SlicerError,
    check_text,
    exact_slice,
    parse_signature,
    render,
    type_slice,
)


ROOT = Path(__file__).resolve().parents[1]
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


class IntegrationTests(unittest.TestCase):
    def test_meta_trace_exact_and_type(self) -> None:
        for filename in CASES:
            source = (CORPUS / filename).read_text(encoding="utf-8")
            sig = parse_signature(source)
            try:
                trace = collect_meta_trace(source, "target")
            except SlicerError as exc:
                self.skipTest(f"MetaRocq unavailable: {exc}")
            for mode, closure in (("exact", exact_slice), ("type", type_slice)):
                keep = closure(sig, trace, "target")
                sliced = render(
                    sig,
                    keep,
                    admit_target="target" if mode == "type" else None,
                )
                result = check_text(sliced)
                self.assertTrue(
                    result.ok,
                    f"{filename}:{mode} failed:\n{result.output}\n---\n{sliced}",
                )


if __name__ == "__main__":
    unittest.main()
