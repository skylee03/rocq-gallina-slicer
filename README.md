# Rocq + MetaRocq Gallina Slicer

A prototype declaration-level slicer for a **Gallina subset**, using
**MetaRocq / Template Rocq** to obtain dependencies from Rocq's elaborated
kernel environment rather than from `.glob` or source-level identifier matching.

This is the third prototype in the series:

```text
../rocq-proof-slicer      Rocq + .glob
../twelf-proof-slicer     Twelf/LF + type-checker trace
./                        Rocq + MetaRocq + Gallina subset
```

## Why MetaRocq instead of SerAPI?

SerAPI was archived at Coq 8.20 and has no Rocq 9.3 release.  MetaRocq has a
`9.3` branch, and Template Rocq exposes the kernel term and global environment
through `tmQuote`, `tmQuoteConstant`, and `tmQuoteRec`.  This makes it possible
to get **elaborated** dependencies while remaining on Rocq 9.3.

The prototype uses MetaRocq as a dependency oracle and uses `rocq compile` as
the final validation oracle.

## Requirements

- Rocq 9.3
- MetaRocq `rocq-metarocq-template` from the `9.3` branch
- Python 3.10+

Install MetaRocq:

```bash
cd rocq-gallina-slicer
./scripts/install-metarocq.sh
```

The script installs `coq-ext-lib`, pins `rocq-metarocq-utils`,
`rocq-metarocq-common`, and `rocq-metarocq-template` to the MetaRocq `9.3`
branch, and installs the Template plugin.

Install the Python command:

```bash
python3 -m pip install -e .
gallina-slice --help
```

## Quick start

```bash
gallina-slice corpus/nat.v target --mode exact
gallina-slice corpus/nat.v target --mode type
```

Or:

```bash
./run.sh
```

## How it works

### 1. Source blocks

`gallina_slicer/slicer.py` parses a conservative Gallina subset:

- `Definition`, `Fixpoint`, `Theorem`, `Lemma`, `Example`, `Inductive`,
  `Record`, `Axiom`, `Parameter`, `Variable`;
- ordinary `Require`/`Import`/`Open`/`Set` headers;
- theorem proofs written with ordinary commands ending in `Qed`/`Defined`/
  `Admitted`.

The parser groups a theorem statement with its proof script.  It is not a full
Rocq parser and does not attempt tactic-level analysis.

### 2. MetaRocq driver

`gallina_slicer/meta_trace.py` appends a small MetaRocq driver to the input
file.  For target `foo` it prints:

```text
TYPE  <constants in the type of foo>
EXACT <constants in foo's type/body and in the quoted environment>
```

`TYPE` is obtained from `tmQuoteConstant` and `cst_type`.
`EXACT` is obtained from `tmQuoteRec`, which returns the elaborated global
environment and term.  The driver traverses `Ast.term` with
`AstUtils.fold_term`, collecting `tConst`, `tInd`, and `tConstruct` names.

The temporary file is named `input.v`, so local constants are qualified as
`input.foo`.  Only those local names are matched back to source declarations;
imported constants such as `Corelib.Init.Datatypes.nat` are ignored.

### 3. Slicing and validation

- **`--mode exact`** keeps all local declarations in the `EXACT` set, including
  proof-body dependencies.  The target theorem retains its proof.
- **`--mode type`** keeps local declarations in the `TYPE` set.  The target
  theorem is rendered as `... Admitted.` so that proof-only dependencies can be
  dropped.

Every non-`--no-check` slice is compiled with `rocq compile -q`.

## Example

`corpus/nat.v`:

```coq
From Stdlib Require Import Arith.

Definition helper : nat := 1.
Definition unused : nat := 2.

Theorem target : 1 = 1.
Proof.
  change (helper = helper).
  reflexivity.
Qed.
```

The proof of `target` uses `helper`, but its statement does not.

Exact slice:

```coq
Definition helper : nat := 1.
Theorem target : 1 = 1.
Proof.
  change (helper = helper).
  reflexivity.
Qed.
```

Type slice:

```coq
Theorem target : 1 = 1.
Admitted.
```

The exact mode keeps the proof-body dependency; the type mode drops it.

## Corpus

The corpus contains eight small Gallina files:

| file | target | exact | type |
|---|---|---:|---:|
| `nat.v` | `target` | 8 → 3 (62.5%) | 8 → 2 (75.0%) |
| `list.v` | `target` | 8 → 4 (50.0%) | 8 → 4 (50.0%) |
| `bool.v` | `target` | 7 → 3 (57.1%) | 7 → 3 (57.1%) |
| `inductive.v` | `target` | 6 → 5 (16.7%) | 6 → 5 (16.7%) |
| `record.v` | `target` | 10 → 6 (40.0%) | 10 → 6 (40.0%) |
| `fixpoint.v` | `target` | 11 → 7 (36.4%) | 11 → 7 (36.4%) |
| `scope.v` | `target` | 6 → 2 (66.7%) | 6 → 2 (66.7%) |
| `unused.v` | `target` | 7 → 2 (71.4%) | 7 → 2 (71.4%) |

Mean reduction:

- exact: **50.1%** (range 16.7%–71.4%);
- type: **51.7%** (range 16.7%–75.0%).

All sixteen slices compile with `rocq compile -q`.  This is a sanity corpus,
not a benchmark.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 selftest.py
```

The integration tests require Rocq 9.3 plus MetaRocq Template; otherwise they
are skipped or fail with an installation hint.

## Limitations

- The source parser covers a Gallina subset, not full Rocq syntax.  Modules,
  functors, canonical structures, custom notations, and many commands are not
  handled.
- This is **declaration-level** slicing.  It does not slice tactic scripts or
  individual tactic steps.
- `--mode type` only admits the target theorem.  If the target is a
  `Definition` whose body is needed, type mode may fail; use exact mode.
- The trace is a set of constants collected from the elaborated term and
  environment, not a full typing-derivation tree.  It is still much closer to
  the kernel than `.glob` or identifier matching.
- Source rendering keeps whole declarations.  A more precise version could
  print selected subterms and reconstruct Gallina syntax from the kernel term.
- External constants are intentionally filtered out using the temporary
  `input.` module prefix.  If the subset grows to local modules, this mapping
  needs to become module-aware.

## Repository layout

```text
rocq-gallina-slicer/
├── gallina_slicer/
│   ├── slicer.py        # Gallina subset parser + rendering + rocq check
│   ├── meta_trace.py    # MetaRocq driver and trace parser
│   └── cli.py           # gallina-slice
├── corpus/              # eight small .v files
├── scripts/
│   └── install-metarocq.sh
├── tests/
│   ├── test_unit.py
│   └── test_integration.py
├── selftest.py
├── run.sh
├── docs/design.md
├── pyproject.toml
└── LICENSE
```
