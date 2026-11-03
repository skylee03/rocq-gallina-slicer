"""A small Gallina-subset slicer.

Source parsing is deliberately conservative: the supported corpus contains
top-level ``Definition``, ``Theorem``, ``Fixpoint``, ``Inductive``, ``Record``,
``Axiom``, and proof scripts made of ordinary commands.  Dependency discovery is
delegated to MetaRocq (see ``meta_trace.py``); this module handles source
blocks, closure over the local signature, and rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import shutil
import subprocess

class SlicerError(RuntimeError):
    """Raised for malformed input, unknown targets, or failed checks."""


DECL_HEADS = {
    "Definition",
    "Theorem",
    "Lemma",
    "Example",
    "Fact",
    "Remark",
    "Corollary",
    "Proposition",
    "Fixpoint",
    "CoFixpoint",
    "Inductive",
    "CoInductive",
    "Record",
    "Axiom",
    "Parameter",
    "Variable",
    "Constant",
}

THEOREM_HEADS = {
    "Theorem",
    "Lemma",
    "Example",
    "Fact",
    "Remark",
    "Corollary",
    "Proposition",
}

PROOF_END = {"Qed", "Defined", "Admitted", "Abort"}

NAME_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_']*)")


@dataclass
class Block:
    text: str
    head: str
    name: str | None = None
    kind: str = "header"  # "header" or "decl"
    type_text: str = ""
    index: int = 0

    @property
    def is_theorem(self) -> bool:
        return self.head in THEOREM_HEADS


@dataclass
class Signature:
    blocks: list[Block]
    declarations: dict[str, Block] = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        return list(self.declarations)


def strip_comments(text: str) -> str:
    """Remove nested Rocq comments while preserving newlines and strings."""

    out: list[str] = []
    i = 0
    depth = 0
    in_string = False
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    out.append('"')
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        if depth:
            if text.startswith("(*", i):
                depth += 1
                i += 2
            elif text.startswith("*)", i):
                depth -= 1
                i += 2
            else:
                if ch == "\n":
                    out.append("\n")
                i += 1
            continue

        if text.startswith("(*", i):
            depth = 1
            i += 2
            continue
        if ch == '"':
            in_string = True
        out.append(ch)
        i += 1
    return "".join(out)


def split_commands(text: str) -> list[str]:
    """Split at top-level periods outside comments and strings."""

    commands: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    for ch in text:
        if in_string:
            current.append(ch)
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            current.append(ch)
            continue
        if ch in pairs:
            depth += 1
        elif ch in closing:
            depth -= 1
        if ch == "." and depth == 0:
            command = "".join(current).strip()
            if command:
                commands.append(command)
            current = []
        else:
            current.append(ch)
    rest = "".join(current).strip()
    if rest:
        # A missing final period is common in scratch files; accept it and
        # let Rocq report the real error.
        commands.append(rest)
    return commands


def command_head(command: str) -> str:
    stripped = command.lstrip()
    # Drop common attributes such as #[local] or #[universes(...)].
    while stripped.startswith("#["):
        end = stripped.find("]")
        if end < 0:
            break
        stripped = stripped[end + 1 :].lstrip()
    match = re.match(r"([A-Za-z_][A-Za-z0-9_']*)", stripped)
    return match.group(1) if match else ""


def find_top_level(text: str, needle: str) -> int:
    depth = 0
    in_string = False
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
        elif ch in pairs:
            depth += 1
        elif ch in closing:
            depth -= 1
        elif depth == 0 and text.startswith(needle, i):
            return i
        i += 1
    return -1


def declaration_type(text: str, head: str) -> str:
    colon = find_top_level(text, ":")
    if colon < 0:
        return ""
    rest = text[colon + 1 :].strip()
    assign = find_top_level(rest, ":=")
    if assign >= 0:
        rest = rest[:assign]
    if head in {"Inductive", "CoInductive", "Record"}:
        return ""
    return rest.strip()


def parse_signature(source: str) -> Signature:
    commands = split_commands(strip_comments(source))
    blocks: list[Block] = []
    i = 0
    while i < len(commands):
        command = commands[i]
        head = command_head(command)
        if head in DECL_HEADS:
            name_match = NAME_RE.search(command[command.find(head) + len(head) :])
            name = name_match.group(1) if name_match else None
            parts = [command]
            j = i + 1
            if head in THEOREM_HEADS and find_top_level(command, ":=") < 0:
                # Group the theorem statement with its proof script.
                while j < len(commands) and command_head(commands[j]) not in PROOF_END:
                    parts.append(commands[j])
                    j += 1
                if j < len(commands):
                    parts.append(commands[j])
                    j += 1
            text = ". ".join(parts) + "."
            blocks.append(
                Block(
                    text=text,
                    head=head,
                    name=name,
                    kind="decl",
                    type_text=declaration_type(parts[0], head),
                    index=len(blocks),
                )
            )
            i = j
        else:
            blocks.append(Block(text=command + ".", head=head, index=len(blocks)))
            i += 1

    declarations = {
        b.name: b for b in blocks if b.kind == "decl" and b.name is not None
    }
    return Signature(blocks=blocks, declarations=declarations)


def exact_slice(sig: Signature, trace: meta_trace.MetaTrace, target: str) -> set[str]:
    keep = (trace.exact_names & sig.declarations.keys()) | {target}
    return keep


def type_slice(sig: Signature, trace: meta_trace.MetaTrace, target: str) -> set[str]:
    keep = (trace.type_names & sig.declarations.keys()) | {target}
    return keep


def _admit_theorem(block: Block) -> str:
    assert block.name
    return f"{block.head} {block.name} : {block.type_text}. Admitted."


def render(
    sig: Signature,
    keep: set[str],
    *,
    header: str | None = None,
    admit_target: str | None = None,
) -> str:
    lines: list[str] = []
    if header:
        lines.append(f"(* {header} *)")
        lines.append("")
    for block in sig.blocks:
        if block.kind == "header":
            lines.append(block.text)
            lines.append("")
        elif block.name in keep:
            if (
                admit_target is not None
                and block.name == admit_target
                and block.is_theorem
                and block.type_text
            ):
                lines.append(_admit_theorem(block))
            else:
                lines.append(block.text)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@dataclass
class CheckResult:
    ok: bool
    output: str
    command: list[str]


def run_rocq_check(path: str | Path, timeout: int = 120) -> CheckResult:
    path = Path(path).resolve()
    cmd = meta_trace.compiler_command() + [str(path)]
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(path.parent),
        )
    except FileNotFoundError as exc:
        raise SlicerError(f"cannot run {cmd[0]!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SlicerError(f"rocq compile timed out after {timeout}s") from exc
    output = (proc.stdout or "") + (proc.stderr or "")
    return CheckResult(ok=proc.returncode == 0, output=output, command=cmd)


def check_text(text: str, timeout: int = 120) -> CheckResult:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rocq-gallina-check-") as tmp:
        path = Path(tmp) / "slice.v"
        path.write_text(text, encoding="utf-8")
        return run_rocq_check(path, timeout=timeout)


def line_count(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def reduction(before: int, after: int) -> float:
    return 0.0 if before == 0 else 100.0 * (before - after) / before


def tail(text: str, n: int = 40) -> str:
    return "\n".join(text.splitlines()[-n:])


# Imported last to avoid the slicer/meta_trace import cycle.
from . import meta_trace  # noqa: E402
