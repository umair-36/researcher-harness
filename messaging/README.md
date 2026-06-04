# messaging/

A single, dependency-free messaging client (`client.py`) the orchestrator uses
to receive requests and report results. One small interface, swappable
backends, stdlib only.

```text
messaging/
  client.py        # send() / poll() + a small CLI
  inbox/           # localfile backend: drop inbound requests here
  outbox/          # localfile backend: outbound messages land here
```

## Backends

Select with `MESSAGING_BACKEND` in `.env` (via `setup/setup_messaging.sh`):

| Backend | Direction | Config | Notes |
|---------|-----------|--------|-------|
| `localfile` (default) | in + out | — | Reads `inbox/*.txt` (consumed → `*.read`), writes `outbox/`. No external egress. |
| `ntfy` | in + out | `NTFY_TOPIC`, `NTFY_SERVER` | Simple push via [ntfy.sh](https://ntfy.sh). Inbound polling is best-effort. |
| `telegram` | in + out | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `sendMessage` / `getUpdates`. |
| `discord` | out only | `DISCORD_WEBHOOK_URL` | Incoming webhooks can post but not read. |

## CLI

```bash
python3 messaging/client.py backend          # print the active backend
python3 messaging/client.py send "hello"     # send a message
python3 messaging/client.py send "hi" --title "harness"
python3 messaging/client.py poll             # fetch + consume inbound messages (JSON lines)
python3 messaging/client.py test             # send a test message
```

## As a library

```python
import sys; sys.path.insert(0, "messaging")
import client as messaging

env = messaging.load_env()
messaging.send("done", title="harness", env=env)
for m in messaging.poll(env):
    print(m["id"], m["text"])
```

## Notes

- `localfile` keeps everything on the machine — the right default for a
  disposable VM or container. `ntfy`, `telegram`, and `discord` publish content
  to an external service; enable them deliberately and use private credentials.
- Inbound poll markers (ntfy `since`, telegram `offset`) are stored in
  `messaging/.state.json`. Runtime messages and that marker file are
  git-ignored; the `inbox/` and `outbox/` directories are kept via `.gitkeep`.
