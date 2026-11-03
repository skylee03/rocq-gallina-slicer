Record point : Type := {
  x : nat;
  y : nat
}.

Definition origin : point := {| x := 0; y := 0 |}.
Definition unused_point : point := {| x := 1; y := 1 |}.

Theorem target : origin = origin.
Proof.
  reflexivity.
Qed.
