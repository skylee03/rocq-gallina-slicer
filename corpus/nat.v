From Stdlib Require Import Arith.

Definition helper : nat := 1.
Definition unused : nat := 2.

Theorem target : 1 = 1.
Proof.
  change (helper = helper).
  reflexivity.
Qed.
