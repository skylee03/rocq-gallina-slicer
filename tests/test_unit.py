from __future__ import annotations

import unittest

from gallina_slicer.meta_trace import MetaTrace
from gallina_slicer.slicer import (
    exact_slice,
    line_count,
    parse_signature,
    render,
    strip_comments,
    type_slice,
)


SOURCE = """\
From Stdlib Require Import Arith.

Definition helper : nat := 1.
Definition unused : nat := 2.

Theorem target : 1 = 1.
Proof.
  change (helper = helper).
  reflexivity.
Qed.
"""


class ParsingTests(unittest.TestCase):
    def test_nested_comments_and_strings(self) -> None:
        text = '(* a (* nested *) comment *) Definition x : nat := 0. (* "not a comment" *)'
        stripped = strip_comments(text)
        self.assertIn("Definition x : nat := 0.", stripped)
        self.assertNotIn("nested", stripped)
        self.assertNotIn("not a comment", stripped)

    def test_theorem_grouping_and_type(self) -> None:
        sig = parse_signature(SOURCE)
        self.assertEqual(sig.names, ["helper", "unused", "target"])
        target = sig.declarations["target"]
        self.assertTrue(target.is_theorem)
        self.assertEqual(target.type_text, "1 = 1")
        self.assertIn("Qed.", target.text)

    def test_slices_and_admission(self) -> None:
        sig = parse_signature(SOURCE)
        trace = MetaTrace(
            type_names=set(),
            exact_names={"helper", "target"},
            raw="",
            output="",
        )
        exact_keep = exact_slice(sig, trace, "target")
        self.assertEqual(exact_keep, {"helper", "target"})
        type_keep = type_slice(sig, trace, "target")
        self.assertEqual(type_keep, {"target"})

        exact_text = render(sig, exact_keep)
        self.assertIn("Definition helper", exact_text)
        self.assertNotIn("Definition unused", exact_text)
        self.assertIn("Qed.", exact_text)

        type_text = render(sig, type_keep, admit_target="target")
        self.assertNotIn("Definition helper", type_text)
        self.assertIn("Theorem target : 1 = 1. Admitted.", type_text)

    def test_line_count(self) -> None:
        self.assertEqual(line_count("a.\n\nb.\n"), 2)


if __name__ == "__main__":
    unittest.main()
