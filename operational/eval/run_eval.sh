#!/usr/bin/env bash
set -euo pipefail

# TODO_HARNESS_EVAL
#
# Replace this file with a real evaluator for target/repo.
# The last stdout line must be JSON:
# {"score": 0.0, "higher_is_better": true, "summary": "what this score means"}
#
# Usage:
#   ./eval/run_eval.sh target/repo

TARGET_REPO="${1:-target/repo}"

if [[ ! -d "$TARGET_REPO" ]]; then
  echo "{\"score\": 0, \"higher_is_better\": true, \"summary\": \"target repo missing: $TARGET_REPO\"}"
  exit 0
fi

# Safe placeholder: counts passing smoke condition as 0.
# Let the first OpenCode run replace this using paper/ and target/repo.
echo "{\"score\": 0, \"higher_is_better\": true, \"summary\": \"placeholder eval; replace eval/run_eval.sh\"}"
