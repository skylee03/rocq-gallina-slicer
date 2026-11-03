"""Command-line interface for the MetaRocq/Gallina slicer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .meta_trace import collect_meta_trace
from .slicer import (
    SlicerError,
    check_text,
    exact_slice,
    line_count,
    parse_signature,
    reduction,
    render,
    tail,
    type_slice,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gallina-slice",
        description="Slice a Gallina subset using MetaRocq's elaborated environment.",
    )
    p.add_argument("file", type=Path, help="Rocq .v file")
    p.add_argument("target", nargs="?", help="target declaration name")
    p.add_argument(
        "--mode",
        choices=["exact", "type"],
        default="exact",
        help="exact = target's full MetaRocq dependency set; type = target statement cone",
    )
    p.add_argument("-o", "--output", type=Path, help="write sliced file here (default: stdout)")
    p.add_argument("--no-check", action="store_true", help="do not run rocq compile on the slice")
    p.add_argument("--list", action="store_true", help="list declarations and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        source = args.file.read_text(encoding="utf-8")
        sig = parse_signature(source)
    except FileNotFoundError:
        print(f"gallina-slice: no such file: {args.file}", file=sys.stderr)
        return 2
    except (OSError, SlicerError) as exc:
        print(f"gallina-slice: {exc}", file=sys.stderr)
        return 2

    if args.list:
        for block in sig.blocks:
            if block.kind == "decl" and block.name:
                kind = "theorem" if block.is_theorem else block.head.lower()
                print(f"{block.name:24} {kind}")
        return 0

    if not args.target:
        print("gallina-slice: target declaration is required", file=sys.stderr)
        return 2
    if args.target not in sig.declarations:
        print(
            f"gallina-slice: unknown target {args.target!r}. "
            f"Known names: {', '.join(sig.names)}",
            file=sys.stderr,
        )
        return 2

    try:
        trace = collect_meta_trace(source, args.target)
    except SlicerError as exc:
        print(f"gallina-slice: {exc}", file=sys.stderr)
        return 1

    if args.mode == "exact":
        keep = exact_slice(sig, trace, args.target)
    else:
        keep = type_slice(sig, trace, args.target)

    sliced = render(
        sig,
        keep,
        header=f"Sliced from {args.file.name} for target {args.target} ({args.mode})",
        admit_target=args.target if args.mode == "type" else None,
    )

    if args.output:
        args.output.write_text(sliced, encoding="utf-8")
        stream = sys.stdout
    else:
        sys.stdout.write(sliced)
        stream = sys.stderr

    before, after = line_count(source), line_count(sliced)
    print(
        f"gallina-slice: target={args.target} mode={args.mode} "
        f"decls={len(keep)} lines={before}->{after} "
        f"(-{reduction(before, after):.1f}%)",
        file=stream,
    )

    if not args.no_check:
        result = check_text(sliced)
        if result.ok:
            print("gallina-slice: rocq check OK", file=stream)
        else:
            print("gallina-slice: rocq check FAILED", file=stream)
            print(tail(result.output), file=stream)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
