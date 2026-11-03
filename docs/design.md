# Design notes

## What is different from the `.glob` prototype?

`../rocq-proof-slicer` uses `.glob` references and identifier heuristics.  This
prototype asks Rocq's kernel, through MetaRocq, what constants occur in the
elaborated target and in the elaborated environment reachable from it.

The key objects are:

| Rocq/MetaRocq object | Role |
|---|---|
| `tmQuoteConstant kn false` | target type (`cst_type`) and optional body |
| `tmQuoteRec target` | elaborated environment + term |
| `Ast.term` | kernel term with `tConst`, `tInd`, `tConstruct`, ... |
| `Ast.Env.global_env` | quoted declarations for dependencies |
| `rocq compile` | final type-checking oracle |

## Driver

`meta_trace.py` defines a driver in Gallina:

```coq
Fixpoint collect_term_fuel (n : nat) (t : Ast.term) : list kername := ...
Definition collect_term (t : Ast.term) := collect_term_fuel 1024 t.
```

The fuel avoids a structural-recursion problem: `fold_term` traverses immediate
subterms but is not itself a structural recursion principle for `collect_term`.

For a target `foo`, the driver prints:

```text
TYPE  <names in foo's type>
EXACT <names in foo's type/body and in the quoted environment>
```

`EXACT` is produced from:

```coq
p <- tmQuoteRec foo ;;
tmMsg ("EXACT " ++ names_string (collect_program p)).
```

`collect_program` walks the quoted `global_env` declarations and the term.  For
constants it visits `cst_type` and `cst_body`; for inductives the declaration is
kept as a whole by the source slicer, while occurrences in terms contribute the
inductive name via `tInd`/`tConstruct`.

## Local-name filtering

The driver is appended to a temporary file named `input.v`.  Local constants
are therefore printed as `input.foo`, while imported constants are printed as
`Corelib.Init.Datatypes.nat` or `Stdlib.Lists.List.length`.

Only `input.*` names are mapped back to source declarations.  This prevents an
imported `add` from accidentally keeping a local `add` that is unrelated.

## Exact vs type

- `exact`: keep the `EXACT` set.  This includes constants used in the proof body
  and in the environments of dependencies.  The target theorem keeps its proof.
- `type`: keep the `TYPE` set.  The target theorem is replaced by
  `Theorem target : T. Admitted.` so that proof-only dependencies can be
  removed.

For `corpus/nat.v`, `helper` occurs in the proof of `target` but not in its
statement.  Exact keeps `helper`; type drops it.

## Why not SerAPI?

SerAPI's last release targets Coq 8.20 and the project is archived.  Rocq 9.3
has no compatible SerAPI release.  MetaRocq's `9.3` branch provides a quoting
plugin that exposes the same kind of kernel information needed here.  The
prototype therefore uses MetaRocq, not SerAPI.

## What is still missing?

- **Full Gallina parsing.**  The source parser is deliberately small.  It does
  not handle modules, functors, canonical structures, custom notation bodies,
  or arbitrary attributes.
- **Term reconstruction.**  The slicer keeps whole source declarations.  It
  does not print a minimal subterm; that would require a Gallina pretty-printer
  and source-level reconstruction.
- **Full derivation tree.**  `collect_term` collects constants from the
  elaborated term/environment, not every typing-rule application.  This is the
  same distinction as the Twelf trace prototype.
- **Tactic-level slicing.**  Proof scripts are grouped and kept/dropped as
  blocks, not sliced tactic-by-tactic.
- **Semantic proof preservation.**  Type mode admits the target theorem and is
  a statement cone, not a proof-preserving reduction.
- **Large developments.**  `tmQuoteRec` on a large target can be expensive.
  The prototype is intended for small Gallina examples and LLM-sized proofs.
