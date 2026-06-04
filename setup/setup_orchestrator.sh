#!/usr/bin/env bash
# Configure the very lightweight orchestrator (orchestrator/orchestrate.py).
# Pluggable, with no hard default: pick none / nemotron / openclaw / custom.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

echo "== setup: lightweight orchestrator =="
ensure_env

backend="${1:-}"
if [[ -z "$backend" ]]; then
  cat <<EOF
  Backends (no hard default):
    none      rule-based keyword routing, no model, works offline (simplest)
    nemotron  NVIDIA NIM chat model (reuses NVIDIA_API_KEY)
    openclaw  external orchestrator command (you supply the invocation)
    custom    any command: reads a user message on stdin, prints an action JSON
EOF
  prompt backend "orchestrator backend" "none"
fi
backend="$(printf '%s' "$backend" | tr '[:upper:]' '[:lower:]')"

case "$backend" in
  none)
    upsert_env ORCH_BACKEND none
    ok "orchestrator will use rule-based routing"
    ;;
  nemotron)
    upsert_env ORCH_BACKEND nemotron
    orch_model=""
    prompt orch_model "Nemotron NIM model id (verify at build.nvidia.com)" \
      "nvidia/nvidia/llama-3.1-nemotron-nano-8b-v1"
    upsert_env ORCH_MODEL "$orch_model"
    info "Ensure NVIDIA_API_KEY is set (setup/set_model.sh ... <API_KEY> or edit operational/.env)."
    ;;
  openclaw|custom)
    upsert_env ORCH_BACKEND "$backend"
    orch_cmd=""
    prompt orch_cmd "command mapping a stdin message to an action JSON" ""
    if [[ -n "$orch_cmd" ]]; then
      upsert_env ORCH_CMD "$orch_cmd"
    else
      warn "ORCH_CMD left empty; set it in operational/.env before serving"
    fi
    info 'Contract: read the user message on stdin, print on stdout:'
    info '  {"action":"run|status|stop","iterations":N,"reason":"..."}'
    ;;
  *)
    err "unknown backend '$backend'"; exit 1 ;;
esac

grep -qE '^ORCH_ITERATIONS=' "$ENV_FILE"   || upsert_env ORCH_ITERATIONS 1
grep -qE '^ORCH_POLL_SECONDS=' "$ENV_FILE" || upsert_env ORCH_POLL_SECONDS 10

ok "orchestrator backend = $backend"
info "Drive it with: orchestrator/run.sh status | run N | serve"
