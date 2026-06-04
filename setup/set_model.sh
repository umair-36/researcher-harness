#!/usr/bin/env bash
# Set / reset / change the OpenCode model + provider API key in operational/.env.
# The harness reads OPENCODE_MODEL from operational/.env, so this is all it takes
# to switch models; opencode.jsonc only supplies a fallback default.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

usage() {
  cat <<EOF
Usage: setup/set_model.sh <preset|provider/model-id> [API_KEY]

Presets (verify exact ids for your account at build.nvidia.com):
  pro     nvidia/deepseek-ai/deepseek-v4-pro       (NVIDIA_API_KEY)
  flash   nvidia/deepseek-ai/deepseek-v4-flash     (NVIDIA_API_KEY)  lighter / cheaper
  llama   nvidia/meta/llama-3.1-8b-instruct        (NVIDIA_API_KEY)  small free-tier example
  qwen    nvidia/qwen/qwen2.5-coder-32b-instruct   (NVIDIA_API_KEY)  coding-tuned example

Anything containing '/' is treated as a literal provider/model-id.
The optional second argument sets that provider's API key.
EOF
}

echo "== setup: OpenCode model =="
[[ $# -ge 1 ]] || { usage; exit 1; }

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
  *)          key_var="$(printf '%s' "$provider" | tr '[:lower:]' '[:upper:]')_API_KEY" ;;
esac

upsert_env OPENCODE_MODEL "$model"
ok "OPENCODE_MODEL = $model"

if [[ -n "$api_key" ]]; then
  upsert_env "$key_var" "$api_key"
else
  info "API key unchanged. Provide it with: setup/set_model.sh $sel <API_KEY>"
  info "  or edit operational/.env directly: ${key_var}=..."
fi
info "Verify the model id is available for your account. The harness uses OPENCODE_MODEL."
