#!/usr/bin/env bash
# Install OpenCode and prepare .env.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

echo "== setup: OpenCode =="
ensure_env

if command -v opencode >/dev/null 2>&1; then
  ok "opencode already installed: $(opencode --version 2>/dev/null || echo unknown)"
else
  info "installing opencode (https://opencode.ai/install) ..."
  if command -v curl >/dev/null 2>&1; then
    if curl -fsSL https://opencode.ai/install | bash; then
      ok "opencode installed"
    else
      warn "automatic install failed (network policy?). Install manually:"
      warn "  curl -fsSL https://opencode.ai/install | bash"
    fi
  else
    warn "curl not found; install opencode manually: https://opencode.ai/install"
  fi
fi

# Soft check: the kb-researcher subagent extracts text from knowledge_base PDFs with
# pdftotext under OpenCode. Not fatal — text material works without it, and Claude Code
# reads PDFs natively.
if command -v pdftotext >/dev/null 2>&1; then
  ok "pdftotext available (PDF extraction for the kb-researcher subagent)"
else
  warn "pdftotext not found; knowledge_base PDFs can't be text-extracted under OpenCode."
  warn "  Install poppler-utils if you'll use PDFs: apt-get install poppler-utils (or: brew install poppler)."
fi

cat <<'EOF'

  Next:
    1. Authenticate your provider, e.g.:
         opencode auth login --provider nvidia
    2. Choose / change the model:
         setup/set_model.sh pro          # presets: pro, flash, llama, qwen
         setup/set_model.sh nvidia/deepseek-ai/deepseek-v4-flash nvapi-XXXX
    3. Verify the harness is ready:
         python3 harness.py check
EOF
