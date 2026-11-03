From Stdlib Require Import Bool.

Definition helper_bool : bool := true.
Definition unused_bool : bool := false.

Theorem target : negb helper_bool = false.
Proof.
  reflexivity.
Qed.
