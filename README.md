# researcher-harness

A minimal, reusable harness that points an autonomous coding agent (OpenCode)
at a repository and loops on measurable improvements. It carries none of the
target's structure: you drop the code in `target_repo/` and the research
material in `knowledge_base/`, and the harness does the rest.

## Layout

```text
researcher-harness/
  harness.py        # the loop: reset -> OpenCode edits target_repo/ -> eval.sh -> keep/revert
  eval.sh           # the scorer (a stub; the first run writes a real one)
  opencode.jsonc    # OpenCode configuration
  AGENTS.md         # the agent's rules
  knowledge_base/   # papers, notes, directions the agent reads (+ AGENTS.md guidance)
  target_repo/      # the code the agent improves            [you provide, git-ignored]
  setup/            # install OpenCode, set the model + API key, configure the rest
  orchestrator/     # tiny pluggable driver: message -> decide -> harness -> report
  messaging/        # the channel the orchestrator talks over
  state/  runs/     # cumulative memory + per-iteration logs  [runtime, git-ignored]
```

The harness itself is one script. The other three concerns — OpenCode + its API
setup, the orchestrator, and the messaging — each live in their own directory.

## Setup

All configuration lives in a single **`.env`** at the repo root. The `setup/`
scripts manage it for you (they create it from `.env.example` on first use):

```bash
setup/setup_opencode.sh                 # install OpenCode, scaffold .env
setup/set_model.sh pro                  # model preset: pro | flash | llama | qwen,
                                        # or a literal provider/model-id (+ optional API key)
setup/setup_orchestrator.sh none        # none | nemotron | openclaw | custom
setup/setup_messaging.sh localfile      # localfile | ntfy | telegram | discord
```

Authenticate OpenCode if needed, then verify the harness:

```bash
opencode auth login --provider nvidia   # if not already authenticated
python3 harness.py check
```

Put the code and the research material in place:

```bash
git clone <repo-url> target_repo
cp ~/Downloads/paper.pdf knowledge_base/

cat > knowledge_base/directions.md <<'EOF'
Improve the eval score without increasing inference time by more than 10%.
Prefer small, easily reversible changes.
EOF
```

Provide `eval.sh`, or leave the stub and let the first run generate one from
`knowledge_base/` and `target_repo/`.

## The loop

Run one iteration, or many:

```bash
python3 harness.py run
python3 harness.py loop 20
```

Each iteration resets `target_repo/` to the best commit, lets OpenCode make one
change, scores it with `eval.sh`, and keeps the change only if it improved.

Inspect outcomes:

```bash
cat state/best.json
cat state/history.jsonl
ls runs/
```

### Eval contract

`eval.sh` receives the target repo path as its first argument and must print a
single JSON object on its last stdout line:

```bash
./eval.sh target_repo
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
orchestrator/run.sh status          # report best score + recent history
orchestrator/run.sh run 5           # run 5 iterations, then report
orchestrator/run.sh serve           # poll messaging and act until told to stop
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

See `setup/README.md`, `orchestrator/README.md`, `messaging/README.md`, and
`knowledge_base/AGENTS.md` for details.

## Model configuration

`.env.example` defaults to:

```bash
OPENCODE_MODEL=nvidia/deepseek-ai/deepseek-v4-pro
NVIDIA_API_KEY=nvapi-...
```

Switch models with `setup/set_model.sh <preset|provider/model-id> [API_KEY]`.
The harness reads `OPENCODE_MODEL` from `.env`; `opencode.jsonc` only supplies a
fallback default, so the harness logic never depends on the model.

## Safety boundary

Autonomous coding requires shell/edit permissions; run this in a disposable
working tree or container. Keep secrets out of `target_repo/` and
`knowledge_base/`. The default messaging backend (`localfile`) sends nothing off
the machine; `ntfy`, `telegram`, and `discord` publish content to an external
service — enable them deliberately.
