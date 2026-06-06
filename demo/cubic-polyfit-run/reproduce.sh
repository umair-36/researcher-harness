#!/usr/bin/env bash
# Reproduce the cubic-polyfit demo end-to-end (see ../../RUNBOOK.md).
#
# Idempotent, re-runnable setup: install OpenCode, configure the model + env,
# clone the target, build the venv + deps, seed the knowledge base, install the
# captured evaluator, and verify. The actual loop (which hits the model API) is
# opt-in behind --run.
set -euo pipefail

# _lib.sh resolves REPO_ROOT from its own location, so this works regardless of
# the caller's cwd or where this script lives in the tree.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../../setup/_lib.sh"
cd "$REPO_ROOT"   # all RUNBOOK commands are relative to the harness root

usage() {
  cat <<EOF
Usage:
  demo/cubic-polyfit-run/reproduce.sh [OPENROUTER_API_KEY] [--run]

  OPENROUTER_API_KEY  optional; also read from \$OPENROUTER_API_KEY.
                      If absent, the model/key step is skipped (existing .env kept).
  --run               after setup, run the first iteration (hits the model API).
                      Also enabled with CUBIC_DEMO_RUN=1. The loop is never run
                      automatically.
  -h, --help          show this help.

Targets https://github.com/Meta2096/cubic-polyfit with a free OpenRouter model.
EOF
}

# --- args: a lone positional is the key; --run is a flag (never the key). -------
DO_RUN="${CUBIC_DEMO_RUN:-0}"
KEY=""
for arg in "$@"; do
  case "$arg" in
    --run)     DO_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    -*)        err "unknown flag: $arg"; usage; exit 1 ;;
    *)         if [[ -z "$KEY" ]]; then KEY="$arg"; else err "unexpected extra arg: $arg"; exit 1; fi ;;
  esac
done
KEY="${KEY:-${OPENROUTER_API_KEY:-}}"

echo "== reproduce: cubic-polyfit demo =="

# --- preflight ------------------------------------------------------------------
info "step 0/8: preflight"
missing=0
for tool in python3 git curl; do
  if command -v "$tool" >/dev/null 2>&1; then ok "$tool found"; else err "$tool not found"; missing=1; fi
done
[[ "$missing" -eq 0 ]] || { err "install the missing tools above and re-run"; exit 1; }
command -v pdftotext >/dev/null 2>&1 || warn "pdftotext not found; KB PDF extraction unavailable under OpenCode (not fatal)"

# --- 1. OpenCode ----------------------------------------------------------------
info "step 1/8: install opencode"
if command -v opencode >/dev/null 2>&1; then
  ok "opencode already installed"
else
  "$REPO_ROOT/setup/setup_opencode.sh" || warn "opencode install reported a problem (network policy?); continuing"
fi

# --- 2. model + env -------------------------------------------------------------
info "step 2/8: configure model + env"
if [[ -n "$KEY" ]]; then
  "$REPO_ROOT/setup/set_model.sh" openrouter/openai/gpt-oss-20b:free "$KEY"
else
  warn "no OpenRouter key (arg or \$OPENROUTER_API_KEY); leaving existing .env model/key untouched"
  warn "  set it later: setup/set_model.sh openrouter/openai/gpt-oss-20b:free <KEY>"
fi
"$REPO_ROOT/setup/set_model.sh" fallback "opencode/deepseek-v4-flash-free,opencode/big-pickle"
upsert_env MPLBACKEND Agg

# --- 3. clone target (before pip; the install reads its requirements) -----------
info "step 3/8: clone target_repo"
if [[ -d target_repo && -n "$(ls -A target_repo 2>/dev/null)" ]]; then
  ok "target_repo already present; skipping clone"
else
  if git clone https://github.com/Meta2096/cubic-polyfit target_repo; then
    ok "cloned cubic-polyfit"
  else
    err "git clone failed (network policy?). Clone manually then re-run:"
    err "  git clone https://github.com/Meta2096/cubic-polyfit target_repo"
    exit 1
  fi
fi

# --- 4. venv + deps -------------------------------------------------------------
info "step 4/8: python venv + deps"
if [[ -x .venv/bin/python ]]; then
  ok ".venv already exists; skipping create"
else
  python3 -m venv --without-pip .venv || { err "venv creation failed"; exit 1; }
fi
if .venv/bin/python -m pip --version >/dev/null 2>&1; then
  ok "pip already present in .venv"
else
  if curl -fsSL https://bootstrap.pypa.io/get-pip.py | .venv/bin/python; then
    ok "pip bootstrapped"
  else
    err "get-pip.py failed (network policy?); install pip into .venv manually, then re-run"
    exit 1
  fi
fi
if MPLBACKEND=Agg .venv/bin/pip install -r target_repo/requirements.txt; then
  ok "target deps installed"
else
  err "pip install failed (network policy?); resolve and re-run"
  exit 1
fi

# --- 5. seed knowledge base -----------------------------------------------------
info "step 5/8: seed knowledge_base/library"
mkdir -p knowledge_base/library
if [[ -f knowledge_base/library/base_paper.pdf ]]; then
  ok "base_paper.pdf already seeded"
elif [[ -f target_repo/base_paper.pdf ]]; then
  cp target_repo/base_paper.pdf knowledge_base/library/base_paper.pdf
  ok "copied base_paper.pdf into knowledge_base/library"
else
  warn "target_repo/base_paper.pdf not found; KB PDF not seeded"
fi

# --- 6. install the captured evaluator ------------------------------------------
# The tracked root eval.sh is the generic stub; install this demo's cubic-specific
# evaluator so reproduction is deterministic (no reliance on the worker regenerating it).
info "step 6/8: install captured eval.sh"
cp "$SCRIPT_DIR/eval.sh" "$REPO_ROOT/eval.sh"
chmod +x "$REPO_ROOT/eval.sh"
ok "installed demo eval.sh at repo root"

# --- 7. verify ------------------------------------------------------------------
info "step 7/8: verify harness"
export MPLBACKEND=Agg
export PATH="$HOME/.opencode/bin:$PATH"
.venv/bin/python harness.py check || warn "harness check reported issues (review output above)"

# --- 8. loop (opt-in) -----------------------------------------------------------
if [[ "$DO_RUN" == "1" ]]; then
  info "step 8/8: running first iteration (hits the model API)"
  .venv/bin/python harness.py run
else
  info "step 8/8: skipped (loop hits the model API). Re-run with --run to start it."
  cat <<EOF

  Setup complete. Next, in your shell:
    export PATH="\$HOME/.opencode/bin:\$PATH"
    source .venv/bin/activate
    export MPLBACKEND=Agg
    python3 harness.py run        # first iteration
    python3 harness.py loop 5     # 5 more iterations
EOF
fi
