#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p paper directions target/repo eval scripts state runs

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it before running unattended iterations."
fi

chmod +x eval/run_eval.sh scripts/*.sh 2>/dev/null || true

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode is not installed."
  echo "Install with: curl -fsSL https://opencode.ai/install | bash"
  echo "Then authenticate, e.g.: opencode auth login --provider nvidia"
else
  opencode --version || true
fi

python3 scripts/harness.py --check
echo "Setup check complete."
