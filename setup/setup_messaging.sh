#!/usr/bin/env bash
# Configure the messaging mechanism the orchestrator uses (messaging/client.py).
# Default localfile needs no external service; ntfy/telegram/discord are opt-in.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

echo "== setup: messaging =="
ensure_env

backend="${1:-}"
if [[ -z "$backend" ]]; then
  cat <<EOF
  Backends:
    localfile  inbox/outbox files under messaging/ (default; no external egress)
    ntfy       ntfy.sh topic            (simple push; optional inbound)
    telegram   Telegram bot             (sendMessage / getUpdates)
    discord    Discord incoming webhook (send-only)
EOF
  prompt backend "messaging backend" "localfile"
fi
backend="$(printf '%s' "$backend" | tr '[:upper:]' '[:lower:]')"
upsert_env MESSAGING_BACKEND "$backend"

case "$backend" in
  localfile)
    mkdir -p "$REPO_ROOT/messaging/inbox" "$REPO_ROOT/messaging/outbox"
    ok "inbox/outbox ready under messaging/"
    info "Drop a request: echo 'run 3' > messaging/inbox/req.txt"
    ;;
  ntfy)
    ntfy_topic=""; ntfy_server=""
    prompt ntfy_topic  "ntfy topic name" ""
    prompt ntfy_server "ntfy server"     "https://ntfy.sh"
    [[ -n "$ntfy_topic" ]] && upsert_env NTFY_TOPIC "$ntfy_topic" || warn "NTFY_TOPIC left empty"
    upsert_env NTFY_SERVER "$ntfy_server"
    warn "ntfy sends content to an external service; use a private/unguessable topic."
    ;;
  telegram)
    tg_token=""; tg_chat=""
    prompt tg_token "Telegram bot token" ""
    prompt tg_chat  "Telegram chat id"   ""
    [[ -n "$tg_token" ]] && upsert_env TELEGRAM_BOT_TOKEN "$tg_token" || warn "TELEGRAM_BOT_TOKEN left empty"
    [[ -n "$tg_chat"  ]] && upsert_env TELEGRAM_CHAT_ID   "$tg_chat"  || warn "TELEGRAM_CHAT_ID left empty"
    ;;
  discord)
    dc_hook=""
    prompt dc_hook "Discord webhook URL" ""
    [[ -n "$dc_hook" ]] && upsert_env DISCORD_WEBHOOK_URL "$dc_hook" || warn "DISCORD_WEBHOOK_URL left empty"
    info "Discord webhooks are send-only; the orchestrator can report but not receive."
    ;;
  *)
    err "unknown backend '$backend'"; exit 1 ;;
esac

ok "messaging backend = $backend"
if [[ -t 0 ]]; then
  read -r -p "  send a test message now? [y/N]: " yn || true
  [[ "${yn:-}" =~ ^[Yy] ]] && { python3 "$REPO_ROOT/messaging/client.py" test || warn "test send failed"; }
else
  info "Test later with: python3 messaging/client.py test"
fi
