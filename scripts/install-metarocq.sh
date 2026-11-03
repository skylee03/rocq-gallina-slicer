#!/usr/bin/env bash
# Install the MetaRocq Template plugin for Rocq 9.3.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$ROOT/.metarocq-src}"
BRANCH="9.3"

if ! command -v opam >/dev/null 2>&1; then
  echo "opam not found" >&2
  exit 2
fi

if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch "$BRANCH" \
    https://github.com/MetaRocq/metarocq.git "$SRC"
fi

opam install -y coq-ext-lib
for pkg in rocq-metarocq-utils rocq-metarocq-common rocq-metarocq-template; do
  opam pin add -y -n "$pkg" "$SRC"
done
opam install -y rocq-metarocq-template

echo
echo "MetaRocq Template installed for Rocq 9.3"
