From Stdlib Require Import List.
Import ListNotations.

Definition helper_list : list nat := 1 :: nil.
Definition unused_list : list nat := 2 :: nil.

Theorem target : length helper_list = 1.
Proof.
  reflexivity.
Qed.
