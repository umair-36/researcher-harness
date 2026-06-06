#!/usr/bin/env bash
# Usage: ./eval.sh target_repo

set -euo pipefail

if [ "${1:-}" = "" ]; then
    echo "Usage: $0 <repo_path>" >&2
    exit 1
fi

REPO="$1"

# Run the cubic fit script which produces metrics.csv in outputs
PYTHON="$(command -v python3 || command -v python)"
if [ -z "$PYTHON" ]; then
    echo "Python not found" >&2
    exit 1
fi

$PYTHON "$REPO/src/cubic_fit.py"

METRICS_CSV="$REPO/outputs/metrics.csv"
if [ ! -f "$METRICS_CSV" ]; then
    echo "Metrics file not found: $METRICS_CSV" >&2
    exit 1
fi

# Extract RMSE from the second line (CSV header: RMSE,MAE,R2 — column 1 is RMSE)
RMSE=$(awk -F',' 'NR==2{print $1}' "$METRICS_CSV")

# Output JSON according to contract
printf '{"score": %s, "higher_is_better": false, "summary": "RMSE from cubic fit"}\n' "$RMSE"
