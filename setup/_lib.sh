#!/usr/bin/env bash
# Shared helpers for the setup/ scripts. Source this, do not run it directly.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
ENV_EXAMPLE="$REPO_ROOT/.env.example"

info() { printf '  - %s\n' "$*"; }
ok()   { printf '  [ok] %s\n' "$*"; }
warn() { printf '  [warn] %s\n' "$*" >&2; }
err()  { printf '  [err] %s\n' "$*" >&2; }

# Create .env from the example (or empty) if it is missing.
ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      cp "$ENV_EXAMPLE" "$ENV_FILE"
      info "created .env from .env.example"
    else
      : > "$ENV_FILE"
      info "created empty .env"
    fi
  fi
}

# upsert_env KEY VALUE  -> set KEY=VALUE in .env (replace or append).
upsert_env() {
  local key="$1" val="$2" esc
  ensure_env
  if grep -qE "^${key}=" "$ENV_FILE"; then
    esc=$(printf '%s' "$val" | sed -e 's/[\\/&]/\\&/g')
    sed -i "s/^${key}=.*/${key}=${esc}/" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
  ok "set ${key}"
}

# prompt VAR "label" "default" -> read into VAR, using default when non-interactive.
prompt() {
  local __var="$1" label="$2" default="${3:-}" reply=""
  if [[ -t 0 ]]; then
    read -r -p "  ${label} [${default}]: " reply || true
  fi
  printf -v "$__var" '%s' "${reply:-$default}"
}
