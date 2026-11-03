From Stdlib Require Import Arith.

Fixpoint double (n : nat) : nat :=
  match n with
  | 0 => 0
  | S k => S (S (double k))
  end.

Definition unused : nat := double 5.

Theorem target : double 0 = 0.
Proof.
  reflexivity.
Qed.
