#!/usr/bin/env bash
# Set / reset / change the OpenCode model + provider API key in .env.
# The harness reads OPENCODE_MODEL from .env, so this is all it takes
# to switch models; opencode.jsonc only supplies a fallback default.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

usage() {
  cat <<EOF
Usage:
  setup/set_model.sh <preset|provider/model-id> [API_KEY]   set the preferred model
  setup/set_model.sh fallback "<m1,m2,...>"                  set the fallback chain ("" clears)
  setup/set_model.sh list                                    list available model ids

Presets (verify exact ids for your account at build.nvidia.com):
  pro     nvidia/deepseek-ai/deepseek-v4-pro       (NVIDIA_API_KEY)
  flash   nvidia/deepseek-ai/deepseek-v4-flash     (NVIDIA_API_KEY)  lighter / cheaper
  llama   nvidia/meta/llama-3.1-8b-instruct        (NVIDIA_API_KEY)  small free-tier example
  qwen    nvidia/qwen/qwen2.5-coder-32b-instruct   (NVIDIA_API_KEY)  coding-tuned example

Anything containing '/' is treated as a literal provider/model-id, e.g. a free
OpenCode Zen model: setup/set_model.sh opencode/big-pickle
The optional second argument sets that provider's API key.

Fallback: OPENCODE_FALLBACK_MODELS is tried in order when the preferred model fails
(e.g. NVIDIA NIM overloaded). Free OpenCode Zen ids (opencode/<id>) make good
fallbacks — 'setup/set_model.sh list' or https://opencode.ai/zen for current ids:
  setup/set_model.sh fallback "opencode/big-pickle,opencode/nemotron-3-super"
EOF
}

echo "== setup: OpenCode model =="
[[ $# -ge 1 ]] || { usage; exit 1; }

# Subcommands: manage the fallback chain, or list available models.
case "$1" in
  fallback)
    [[ $# -ge 2 ]] || { err "usage: setup/set_model.sh fallback \"m1,m2,...\"  (use \"\" to clear)"; exit 1; }
    upsert_env OPENCODE_FALLBACK_MODELS "$2"
    if [[ -n "$2" ]]; then
      ok "OPENCODE_FALLBACK_MODELS = $2"
      info "Tried in order when the preferred model fails (e.g. NIM overloaded)."
    else
      ok "OPENCODE_FALLBACK_MODELS cleared (fallback disabled)"
    fi
    exit 0
    ;;
  list)
    if command -v opencode >/dev/null 2>&1; then
      info "opencode/<id> entries are OpenCode Zen models; the free set rotates."
      opencode models || { err "could not list models — is OpenCode authenticated ('opencode auth login')?"; exit 1; }
    else
      err "opencode is not installed; run setup/setup_opencode.sh first"
      info "Free model ids are also listed at https://opencode.ai/zen"
      exit 1
    fi
    exit 0
    ;;
esac

sel="$1"; api_key="${2:-}"
case "$sel" in
  -h|--help) usage; exit 0 ;;
  pro)   model="nvidia/deepseek-ai/deepseek-v4-pro" ;;
  flash) model="nvidia/deepseek-ai/deepseek-v4-flash" ;;
  llama) model="nvidia/meta/llama-3.1-8b-instruct" ;;
  qwen)  model="nvidia/qwen/qwen2.5-coder-32b-instruct" ;;
  */*)   model="$sel" ;;
  *)     err "unknown preset '$sel' (and not a provider/model id)"; usage; exit 1 ;;
esac

provider="${model%%/*}"
case "$provider" in
  nvidia)     key_var="NVIDIA_API_KEY" ;;
  openai)     key_var="OPENAI_API_KEY" ;;
  anthropic)  key_var="ANTHROPIC_API_KEY" ;;
  openrouter) key_var="OPENROUTER_API_KEY" ;;
  opencode)   key_var="" ;;  # OpenCode Zen authenticates via `opencode auth login`
  *)          key_var="$(printf '%s' "$provider" | tr '[:lower:]' '[:upper:]')_API_KEY" ;;
esac

upsert_env OPENCODE_MODEL "$model"
ok "OPENCODE_MODEL = $model"

if [[ -z "$key_var" ]]; then
  info "Provider '$provider' authenticates via 'opencode auth login' (no API key var needed)."
elif [[ -n "$api_key" ]]; then
  upsert_env "$key_var" "$api_key"
else
  info "API key unchanged. Provide it with: setup/set_model.sh $sel <API_KEY>"
  info "  or edit .env directly: ${key_var}=..."
fi
info "Verify the model id is available for your account. The harness uses OPENCODE_MODEL."
