#!/usr/bin/env bash
set -euo pipefail

N="${1:-10}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

completed=0
for i in $(seq 1 "$N"); do
  echo "=== research-harness iteration $i / $N ==="
  if ! python3 scripts/harness.py run; then
    echo "research-harness: iteration $i failed (exit $?); stopping after $completed completed." >&2
    exit 1
  fi
  completed=$((completed + 1))
done
echo "research-harness: completed $completed / $N iterations."
