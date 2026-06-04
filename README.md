# researcher-harness

A minimal agentic research loop around an existing code repository.

The loop itself is deliberately boring: OpenCode proposes and edits code,
`eval/run_eval.sh` scores it, the harness records the result, keeps
improvements, and reverts failures. A very lightweight orchestrator can drive
that loop on your behalf and report progress over a messaging channel.

## Top-level layout

```text
researcher-harness/
  operational/     # the research loop engine + everything it operates on
  setup/           # bootstrap & configuration scripts (run these first)
  orchestrator/    # very lightweight, pluggable loop driver
  messaging/       # the channel the orchestrator talks over
  README.md  LICENSE  INSTRUCTIONS.md
```

Four scope-specific directories:

| Directory | What it is |
|-----------|------------|
| `operational/` | The harness root. Contains the engine (`scripts/`, `eval/`), its inputs (`paper/`, `directions/`, `target/`), its memory (`state/`, `runs/`), the example set, and the OpenCode config (`opencode.jsonc`, `AGENTS.md`, `.env`). |
| `setup/` | One-time bootstrap: install OpenCode, set/reset the model + API key, configure the orchestrator and the messaging mechanism. |
| `orchestrator/` | A tiny, pluggable layer above the loop: it reads requests from messaging, decides an action, runs the harness, and reports back. |
| `messaging/` | A dependency-free messaging client with swappable backends (local file, ntfy, Telegram, Discord). |

### operational/

```text
operational/
  opencode.jsonc   AGENTS.md   .env.example   # OpenCode config + agent rules
  scripts/         setup.sh run_once.sh loop.sh harness.py test_harness.sh
  eval/            run_eval.sh                 # user-provided eval, or generated on first run
  paper/           # the paper, notes, or links
  directions/      # optional human-written research directions
  target/          # clone/copy the open-source code into target/repo
  state/           # machine-readable cumulative memory
  runs/            # per-iteration logs, diffs, eval output
  examples/        # self-contained toy-classifier example
```

## Setup

All configuration lives in **`operational/.env`**. The `setup/` scripts manage
it for you (they create it from `operational/.env.example` on first use):

```bash
setup/setup_opencode.sh                 # install OpenCode, scaffold operational/.env
setup/set_model.sh pro                  # model preset: pro | flash | llama | qwen,
                                        # or a literal provider/model-id (+ optional API key)
setup/setup_orchestrator.sh none        # none | nemotron | openclaw | custom
setup/setup_messaging.sh localfile      # localfile | ntfy | telegram | discord
```

Then finish the harness setup and authenticate OpenCode if needed:

```bash
operational/scripts/setup.sh

# if OpenCode is not yet authenticated:
opencode auth login --provider nvidia
```

Put the target code, the paper, and any direction files in place:

```bash
rm -rf operational/target/repo
git clone <paper-code-repo-url> operational/target/repo
cp ~/Downloads/paper.pdf operational/paper/

cat > operational/directions/ideas.md <<'EOF'
Improve the eval score without increasing inference time by more than 10%.
Prefer small, easily reversible changes.
EOF
```

Provide `operational/eval/run_eval.sh`, or leave the stub and let the first
OpenCode run generate one from the paper and target repo.

## The operational loop

Run one iteration, or many:

```bash
operational/scripts/run_once.sh
operational/scripts/loop.sh 20
```

Inspect outcomes:

```bash
cat operational/state/history.jsonl
cat operational/state/best.json
ls operational/runs/
```

### Eval contract

`operational/eval/run_eval.sh` receives the target repo path as its first
argument and must print a single JSON object on its last stdout line:

```bash
./eval/run_eval.sh target/repo
```

```json
{"score": 0.123, "higher_is_better": false, "summary": "validation loss"}
```

Use `higher_is_better: true` for accuracy, pass rate, reward, etc.; `false` for
loss, error, runtime, etc.

## Orchestrator

A tiny driver that turns a user request into harness activity and reports back.
The decision backend is **pluggable with no hard default** (`ORCH_BACKEND`):

| Backend | Behaviour |
|---------|-----------|
| `none` | Rule-based keyword routing. No model, works offline. |
| `nemotron` | An NVIDIA NIM chat model (`ORCH_MODEL`, reuses `NVIDIA_API_KEY`). |
| `openclaw` / `custom` | An external command (`ORCH_CMD`): user message on stdin → an action JSON on stdout. |

An action is `{"action": "run"|"status"|"stop", "iterations": N, "reason": "…"}`.

```bash
orchestrator/run.sh status        # report best score + recent history
orchestrator/run.sh run 5         # run 5 iterations, then report
orchestrator/run.sh serve         # poll messaging and act until told to stop
orchestrator/run.sh decide "run 3"  # debug: show how a message routes
```

## Messaging

The orchestrator reads requests and sends reports through a single,
dependency-free client (`messaging/client.py`). Pick a backend with
`MESSAGING_BACKEND`:

| Backend | Direction | Notes |
|---------|-----------|-------|
| `localfile` (default) | in + out | `messaging/inbox/` and `messaging/outbox/` files; no external egress. |
| `ntfy` | in + out | An [ntfy.sh](https://ntfy.sh) topic; uses a private topic name. |
| `telegram` | in + out | A Telegram bot (`sendMessage` / `getUpdates`). |
| `discord` | out only | An incoming webhook. |

```bash
echo "run 3" > messaging/inbox/req.txt   # localfile: queue a request
python3 messaging/client.py poll          # fetch + consume inbound messages
python3 messaging/client.py send "hi"     # send a message
python3 messaging/client.py test          # send a test message
```

See `setup/README.md`, `orchestrator/README.md`, and `messaging/README.md` for
details.

## Model configuration

Default `operational/.env.example` uses:

```bash
OPENCODE_MODEL=nvidia/deepseek-ai/deepseek-v4-pro
NVIDIA_API_KEY=nvapi-...
```

Switch models with `setup/set_model.sh <preset|provider/model-id> [API_KEY]`.
The harness reads `OPENCODE_MODEL` from `operational/.env`; `opencode.jsonc`
only supplies a fallback default, so the harness logic never depends on the
model.

## Safety boundary

Autonomous coding requires shell/edit permissions; run this in a disposable
working tree or container. Keep secrets out of `operational/target/repo`,
`operational/paper`, and `operational/directions`. The default messaging
backend (`localfile`) sends nothing off the machine; `ntfy`, `telegram`, and
`discord` publish content to an external service — enable them deliberately.
