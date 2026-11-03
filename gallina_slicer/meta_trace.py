"""MetaRocq-based dependency extraction.

Rocq 9.3 has no compatible SerAPI release: SerAPI was archived at Coq 8.20.
MetaRocq has a 9.3 branch and exposes Rocq's kernel term/environment through
Template Rocq's quoting monad.  We append a small MetaRocq driver to the input
file, compile it, and parse the dependency sets it prints.

For a target constant ``foo`` the driver prints:

    TYPE  <constants in foo's type>
    EXACT <constants in foo's type/body and in the quoted environment>

The exact set is produced by ``tmQuoteRec`` and therefore comes from Rocq's
elaborated term/environment, not from source-level identifier matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

from .slicer import SlicerError, tail


DRIVER_PREFIX = r"""
From MetaRocq.Template Require Import All.
From MetaRocq.Template Require Import AstUtils.
From MetaRocq.Utils Require Import utils.
From MetaRocq.Common Require Import Kernames.
Import MonadNotation.
Import ListNotations.
Local Open Scope bs_scope.

Fixpoint collect_term_fuel (n : nat) (t : Ast.term) : list Kernames.kername :=
  match n with
  | 0 => []
  | S n' =>
      let acc :=
        match t with
        | Ast.tConst kn _ => [kn]
        | Ast.tInd ind _ => [Kernames.inductive_mind ind]
        | Ast.tConstruct ind _ _ => [Kernames.inductive_mind ind]
        | _ => []
        end in
      AstUtils.fold_term
        (fun acc sub => List.app (collect_term_fuel n' sub) acc) acc t
  end.

Definition collect_term (t : Ast.term) : list Kernames.kername :=
  collect_term_fuel 1024 t.

Definition collect_cb (cb : Ast.Env.constant_body) : list Kernames.kername :=
  List.app (collect_term (Ast.Env.cst_type cb))
    (match Ast.Env.cst_body cb with Some b => collect_term b | None => [] end).

Fixpoint collect_decls (ds : list (Kernames.kername * Ast.Env.global_decl)) : list Kernames.kername :=
  match ds with
  | [] => []
  | (_, Ast.Env.ConstantDecl cb) :: rest =>
      List.app (collect_cb cb) (collect_decls rest)
  | (_, Ast.Env.InductiveDecl _) :: rest => collect_decls rest
  end.

Definition collect_program (p : Ast.Env.program) : list Kernames.kername :=
  let '(env, t) := p in
  List.app (collect_decls (Ast.Env.declarations env)) (collect_term t).

Definition names_string (ns : list Kernames.kername) : string :=
  String.concat " " (List.map Kernames.string_of_kername ns).
"""


@dataclass
class MetaTrace:
    type_names: set[str]
    exact_names: set[str]
    raw: str
    output: str


def compiler_command() -> list[str]:
    rocq = os.environ.get("ROCQ") or shutil.which("rocq")
    if not rocq:
        raise SlicerError("rocq not found; put it on PATH or set ROCQ")
    return [rocq, "compile", "-q"]


LOCAL_MODULE = "input"


def local_name(name: str) -> str | None:
    """Return a local declaration name, ignoring imported constants.

    The trace is produced from a temporary file named ``input.v``, so local
    constants are qualified as ``input.foo``.  Imported constants (for example
    ``Corelib.Init.Datatypes.nat``) are not source declarations and must not be
    confused with a same-named local declaration.
    """

    prefix = LOCAL_MODULE + "."
    if name.startswith(prefix):
        return name[len(prefix) :]
    return None


def _driver(target: str) -> str:
    # The target is inserted into a Coq string literal.  Target names in the
    # supported subset are simple identifiers, but escape quotes defensively.
    literal = target.replace('"', '""')
    return (
        DRIVER_PREFIX
        + "\nMetaRocq Run (\n"
        + f'  tmBind (tmLocate1 "{literal}") (fun gr =>\n'
        + "    match gr with\n"
        + "    | Kernames.ConstRef kn =>\n"
        + "        tmBind (tmQuoteConstant kn false) (fun cb =>\n"
        + '          tmBind (tmMsg ("TYPE " ++ names_string (collect_term (Ast.Env.cst_type cb)))) (fun _ =>\n'
        + "            tmBind (tmQuoteRec " + target + ") (fun p =>\n"
        + '              tmMsg ("EXACT " ++ names_string (collect_program p)))))\n'
        + '    | _ => tmFail "target is not a constant"\n'
        + "    end)).\n"
    )


def build_driver(source: str, target: str) -> str:
    return source.rstrip() + "\n\n" + _driver(target)


def parse_meta_output(output: str) -> MetaTrace:
    type_names: set[str] = set()
    exact_names: set[str] = set()
    for line in output.splitlines():
        if line.startswith("TYPE "):
            type_names.update(
                name for n in line[5:].split() if (name := local_name(n)) is not None
            )
        elif line.startswith("EXACT "):
            exact_names.update(
                name for n in line[6:].split() if (name := local_name(n)) is not None
            )
    return MetaTrace(type_names=type_names, exact_names=exact_names, raw="", output=output)


def collect_meta_trace(
    source: str,
    target: str,
    timeout: int = 120,
) -> MetaTrace:
    """Compile source+driver with Rocq/MetaRocq and return dependency sets."""

    cmd = compiler_command()
    with tempfile.TemporaryDirectory(prefix="rocq-gallina-") as tmp:
        path = Path(tmp) / "input.v"
        path.write_text(build_driver(source, target), encoding="utf-8")
        try:
            proc = subprocess.run(
                cmd + [path.name],
                cwd=tmp,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise SlicerError(f"cannot run {cmd[0]!r}: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise SlicerError(f"rocq compile timed out after {timeout}s") from exc

        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            raise SlicerError("MetaRocq trace failed:\n" + tail(output))
        trace = parse_meta_output(output)
        if not trace.exact_names:
            raise SlicerError(
                "MetaRocq produced no EXACT trace; is rocq-metarocq-template "
                "installed?\n" + tail(output)
            )
        trace.raw = build_driver(source, target)
        return trace
