# researcher-harness

A minimal, reusable harness that points an autonomous coding agent (OpenCode)
at a repository and loops on measurable improvements. It carries none of the
target's structure: you drop the code in `target_repo/` and the research
material in `knowledge_base/`, and the harness does the rest.

**Motivated by** [Andrej Karpathy's autoresearch](https://github.com/karpathy/autoresearch) —
the idea of using an autonomous agent in a tight eval-gated loop to iteratively
improve a codebase or model, with the human setting goals and the machine doing
the search. This repo is an attempt to build that loop into a reusable, configurable
harness with pluggable agents, orchestrators, and messaging backends.

---

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

## Knowledge base

Drop papers, notes, and directions into `knowledge_base/`. To keep the agent's context
clean as the material grows, the harness **inlines small text notes in full** and lists
everything else (large notes, PDFs, anything under `knowledge_base/library/`) in a
**manifest**. For those, the agent delegates to a built-in **`kb-researcher` subagent**,
which reads the material in its own isolated context and returns only the distilled facts
it was asked for — so a 50-page PDF never lands in the main loop's context. This is wired
in automatically for OpenCode (an `agent` block in `opencode.jsonc`) and for manual Claude
Code use (`.claude/agents/kb-researcher.md`); no setup required. The extractor defaults to a
lighter, cheaper model.

Optional knobs (all have sane defaults): `KB_INLINE_MAX_BYTES` and `KB_INLINE_TOTAL_BYTES`
control how much text is inlined; `KB_AGENT_MODEL` overrides the extractor's model. PDFs are
extracted with `pdftotext` under OpenCode (install `poppler-utils`); Claude Code reads them
natively. See `knowledge_base/AGENTS.md`.

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
default model id, so the harness logic never depends on the model.

### Falling back to free models

NVIDIA NIM's stronger models are frequently overloaded or unavailable. Set
`OPENCODE_FALLBACK_MODELS` to a comma-separated, ordered list and the harness
retries with the next model whenever the preferred one fails — a nonzero exit, or
a hang past `OPENCODE_TIMEOUT_SECONDS` (set e.g. `1800` to catch a provider that
stalls instead of erroring). Each model that runs is recorded in
`runs/<run_id>/opencode.attempts.txt`, and `python3 harness.py check` prints the
resolved chain.

Free **OpenCode Zen** models (`opencode/<id>`, authenticated once with
`opencode auth login`) make good fallbacks. The free set rotates, so list the
current ids rather than hardcoding them:

```bash
setup/set_model.sh list                                    # = `opencode models`
setup/set_model.sh fallback "opencode/big-pickle,opencode/nemotron-3-super"
```

Leave `OPENCODE_FALLBACK_MODELS` empty to disable fallback (the default). See
https://opencode.ai/zen for the current free models.

**No API key? The open model engages automatically.** A model whose provider
needs a key (e.g. the default `nvidia/...`) is treated as unrunnable when that
key is unset or still the `…REPLACE_ME` placeholder. The harness then skips it
and runs on the free open model (`OPENCODE_OPEN_MODEL`, default an OpenCode Zen
model) — so a fresh checkout with no `NVIDIA_API_KEY` works out of the box once
you `opencode auth login`. `python3 harness.py check` prints the resolved chain
and warns when this kicks in. Set the open model with:

```bash
setup/set_model.sh open opencode/big-pickle
```

## Safety boundary

The harness assumes it runs **in a sandbox** and **headlessly, with no human in
the loop**: OpenCode is invoked with `--dangerously-skip-permissions` by default
(and every tool in `opencode.jsonc` is `allow`) so iterations never block on a
permission prompt. Run it only in a disposable working tree or container, and
keep secrets out of `target_repo/` and `knowledge_base/`. The default messaging
backend (`localfile`) sends nothing off the machine; `ntfy`, `telegram`, and
`discord` publish content to an external service — enable them deliberately.

---

## Changelog

### v0.1 — first end-to-end working version *(current)*

- Verified end-to-end with a cubic polynomial-fitting demo: agent runs, eval fires,
  keep/revert logic works, `state/` and `runs/` populate correctly.
- Python 3.10 compatibility fixes across `harness.py` and supporting scripts.
- Agent model fallback for free-only provider keys (no `NVIDIA_API_KEY` → auto-engages
  the open model).
- Captured demo run outcomes committed to the repo as a reference trace.
- PR review recipe and reproduction script added (`setup/`).

### v0 — harness refactor: minimal structure

- Dropped the `operational/` directory entirely; introduced `target_repo/` and
  `knowledge_base/` as the two external concerns the harness operates on.
- `harness.py` became the single source of truth for the loop (reset → agent edit →
  eval → keep/revert).
- Added headless, sandboxed autonomy defaults (`--dangerously-skip-permissions`,
  all tools `allow` in `opencode.jsonc`).
- `kb-researcher` subagent wired in: large PDFs and notes are extracted in an
  isolated context rather than inlined into the main agent loop.
- `CLAUDE.md` added for manual Claude Code use of the harness.
- `ITERATION.md` split out as a lazy-loaded single-iteration protocol to keep
  `CLAUDE.md` lean.

### Pre-v0 — initial structure and early reorganisation

- **Initial commit**: flat structure, `harness.py` stub, bare `eval.sh`, no
  orchestrator or messaging.
- Bug fixes and tightening of the initial implementation found during a validation
  review.
- Toy-classifier example dataset and an end-to-end test script added.
- First major reorganisation: introduced `operational/`, `setup/`, `orchestrator/`,
  and `messaging/` as separate concerns with their own READMEs.
- Pluggable orchestrator backends (`none`, `nemotron`, `openclaw`/`custom`) and
  pluggable messaging backends (`localfile`, `ntfy`, `telegram`, `discord`).
- Model preset system (`setup/set_model.sh`) and fallback chain
  (`OPENCODE_FALLBACK_MODELS`, `OPENCODE_OPEN_MODEL`).

---

## TODO

### Agent / worker

- [ ] **Claude Code SDK / Agents SDK harness** — a drop-in replacement for the
      OpenCode worker that drives a Claude Code agent programmatically (no shell
      subprocess, structured tool calls, tighter control over the agent's context).
- [ ] **Additional worker backends** — Aider, Cursor background agent, or a raw
      API call with a code-editing scaffold; selectable via `WORKER_BACKEND`.
- [ ] **Router layer** — before handing a task to the worker, a lightweight router
      decides which worker, which model, and how many iterations to budget based on
      task complexity and remaining token/cost budget.

### Eval and scoring

- [ ] **Multi-metric eval** — `eval.sh` currently emits a single scalar; support a
      weighted combination of metrics (loss, throughput, test-pass rate, …) with
      weights set in `.env`.
- [ ] **Eval caching** — skip re-running the eval when `target_repo/` is unchanged
      (hash the tree, cache the result).
- [ ] **Stochastic eval averaging** — run `eval.sh` N times and average to reduce
      noise when the scorer is non-deterministic.

### Harness configuration knobs

- [ ] **Budget controls** — `MAX_COST_USD`, `MAX_TOKENS`, `MAX_WALL_SECONDS` to
      cap runaway loops.
- [ ] **Iteration-level timeouts** — per-iteration wall-clock limit independent of
      the model timeout.
- [ ] **Convergence detection** — stop early when the score hasn't improved in K
      consecutive iterations.
- [ ] **Parallel workers** — run N agents on N clones of `target_repo/` in parallel,
      keep the best result.

### Orchestrator

- [ ] **Claude-as-orchestrator** — replace the rule-based `none` backend with a
      Claude API call that can interpret free-form requests and make richer decisions.
- [ ] **Scheduled runs** — cron-style `ORCH_SCHEDULE` to kick off loops automatically.
- [ ] **Web UI** — a minimal dashboard to view `state/history.jsonl`, trigger runs,
      and inspect `runs/` logs without SSH.

### Tooling and DX

- [ ] **`harness.py replay`** — re-run eval on every commit in `runs/` to reconstruct
      the score history after changing `eval.sh`.
- [ ] **Docker / devcontainer** — a one-command sandbox so users don't need to worry
      about the safety boundary.
- [ ] **GitHub Actions workflow** — run the loop in CI on a schedule or on push,
      commit improvements back to a branch.
