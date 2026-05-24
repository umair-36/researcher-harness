#!/usr/bin/env bash
set -euo pipefail

N="${1:-10}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for i in $(seq 1 "$N"); do
  echo "=== research-harness iteration $i / $N ==="
  python3 scripts/harness.py run
done
