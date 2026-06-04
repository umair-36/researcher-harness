#!/usr/bin/env bash
set -euo pipefail

# TODO_HARNESS_EVAL
#
# Replace this file with a real evaluator for target_repo.
# The last stdout line must be JSON:
# {"score": 0.0, "higher_is_better": true, "summary": "what this score means"}
#
# Usage:
#   ./eval.sh target_repo
#
# Leave the TODO_HARNESS_EVAL marker above in place and the first harness run
# will ask OpenCode to write a real eval from knowledge_base/ and target_repo/.

TARGET_REPO="${1:-target_repo}"

if [[ ! -d "$TARGET_REPO" ]]; then
  echo "{\"score\": 0, \"higher_is_better\": true, \"summary\": \"target repo missing: $TARGET_REPO\"}"
  exit 0
fi

# Safe placeholder until a real evaluator replaces it.
echo "{\"score\": 0, \"higher_is_better\": true, \"summary\": \"placeholder eval; replace eval.sh\"}"
