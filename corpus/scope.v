Definition helper : nat := 1.
Definition unrelated : nat := 2.

Theorem target : helper = 1.
Proof.
  reflexivity.
Qed.
