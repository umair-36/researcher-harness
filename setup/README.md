# setup/

One-time bootstrap and configuration scripts. They all read and write the
single config file **`operational/.env`** (created from
`operational/.env.example` on first use), so the harness, orchestrator, and
messaging client stay in sync.

Run them in this order (each is idempotent and safe to re-run):

| Script | Purpose |
|--------|---------|
| `setup_opencode.sh` | Install OpenCode (`https://opencode.ai/install`) and scaffold `operational/.env`. Prints auth instructions. |
| `set_model.sh <sel> [KEY]` | Set / reset / change the OpenCode model and provider API key. |
| `setup_orchestrator.sh [backend]` | Configure the lightweight orchestrator: `none`, `nemotron`, `openclaw`, or `custom`. |
| `setup_messaging.sh [backend]` | Configure messaging: `localfile`, `ntfy`, `telegram`, or `discord`. |

Each script takes its choice as an argument for non-interactive use, or prompts
when run in a terminal with no argument.

## set_model.sh

```bash
setup/set_model.sh pro                                  # NVIDIA DeepSeek V4 Pro
setup/set_model.sh flash                                # NVIDIA DeepSeek V4 Flash (lighter)
setup/set_model.sh llama                                # small free-tier example
setup/set_model.sh nvidia/qwen/qwen2.5-coder-32b-instruct nvapi-XXXX
```

Presets are convenient labels; any argument containing `/` is treated as a
literal `provider/model-id`. The provider's API key variable is inferred from
the provider prefix (e.g. `nvidia/…` → `NVIDIA_API_KEY`). **Verify the exact
model id is available for your account** (e.g. at build.nvidia.com) — the
harness simply passes `OPENCODE_MODEL` through to OpenCode.

## setup_orchestrator.sh

```bash
setup/setup_orchestrator.sh none        # rule-based, no model, offline-friendly
setup/setup_orchestrator.sh nemotron    # prompts for the NIM model id; reuses NVIDIA_API_KEY
setup/setup_orchestrator.sh openclaw    # prompts for ORCH_CMD (your orchestrator invocation)
setup/setup_orchestrator.sh custom      # prompts for ORCH_CMD (any command)
```

There is no hard default. `openclaw`/`custom` expect a command that reads a user
message on stdin and prints an action JSON on stdout:
`{"action":"run|status|stop","iterations":N,"reason":"..."}`.

## setup_messaging.sh

```bash
setup/setup_messaging.sh localfile      # inbox/outbox files; no external egress (default)
setup/setup_messaging.sh ntfy           # prompts for topic + server
setup/setup_messaging.sh telegram       # prompts for bot token + chat id
setup/setup_messaging.sh discord        # prompts for webhook URL
```

`ntfy`, `telegram`, and `discord` send content to an external service — enable
them deliberately and use private credentials.
