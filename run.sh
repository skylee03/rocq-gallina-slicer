#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m gallina_slicer.cli corpus/nat.v target --mode exact "$@"
