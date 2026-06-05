# researcher-harness Runbook: cubic-polyfit demo

This runbook documents the complete, happy-path setup and operation of
`researcher-harness` targeting `Meta2096/cubic-polyfit` with a free
OpenRouter model.

---

## Prerequisites

The following must be in place before running any commands. Check with `which`:

| Tool     | How to get it |
|----------|---------------|
| `python3` ≥ 3.10 | system package |
| `git`    | system package |
| `curl`   | system package |
| `pdftotext` | `apt install poppler-utils` |

---

## 1. Install OpenCode

```bash
setup/setup_opencode.sh
```

Creates `.env` from `.env.example` and installs the `opencode` binary to
`~/.opencode/bin/`. Add it to your PATH:

```bash
export PATH="$HOME/.opencode/bin:$PATH"
# Add to ~/.bashrc / ~/.zshrc to persist.
```

---

## 2. Configure the model

Pick a free OpenRouter model (list at https://openrouter.ai/models, filter by
`:free`). Set it and the key in `.env`:

```bash
setup/set_model.sh openrouter/openai/gpt-oss-20b:free <OPENROUTER_API_KEY>
```

> **Why `openrouter/openai/gpt-oss-20b:free`?**
> Free Google/Meta models on OpenRouter tend to return HTTP 429 under the large
> system prompts the harness sends. The OpenAI OSS 20B free model responded
> consistently during this demo run. Check current free model availability at
> https://openrouter.ai/models.

Since no NVIDIA key is set, the harness auto-uses the open model. Set a fallback
chain for resilience:

```bash
setup/set_model.sh fallback "opencode/deepseek-v4-flash-free,opencode/big-pickle"
```

Add `MPLBACKEND=Agg` to `.env` for headless matplotlib (no display needed):

```bash
echo "MPLBACKEND=Agg" >> .env
```

---

## 3. Install Python deps

The venv **must** live at the harness root, not under `target_repo/`, because
`git clean -fd` runs inside `target_repo/` at the start of every iteration and
would delete a venv placed there.

```bash
# Bootstrap pip if needed (no system pip)
python3 -m venv --without-pip .venv
curl -fsSL https://bootstrap.pypa.io/get-pip.py | .venv/bin/python

# Install target deps
MPLBACKEND=Agg .venv/bin/pip install -r target_repo/requirements.txt
```

---

## 4. Clone the target repo

```bash
git clone https://github.com/Meta2096/cubic-polyfit target_repo
```

---

## 5. Seed the knowledge base

Copy the paper to `library/` (kept out of the main prompt context, extracted
on-demand by the `kb-researcher` subagent using `pdftotext`):

```bash
mkdir -p knowledge_base/library
cp target_repo/base_paper.pdf knowledge_base/library/base_paper.pdf
```

The three inline notes (`notes.md`, `directions.md`, `background.md`) are already
in `knowledge_base/` and are inlined into every iteration prompt automatically.

---

## 6. Verify the harness

```bash
# Activate the venv so all subprocesses (eval.sh, opencode) inherit the right Python.
source .venv/bin/activate
export MPLBACKEND=Agg
export PATH="$HOME/.opencode/bin:$PATH"

python3 harness.py check
```

Expected output: `Setup check complete.` with a warning that `eval.sh` is still the
placeholder — that is intentional; the first `run` auto-generates it.

---

## 7. Run the loop

### First run (auto-writes eval.sh + baseline + one iteration)

```bash
python3 harness.py run
```

The first run:
1. Asks the worker to write a real `eval.sh` (since the stub has `TODO_HARNESS_EVAL`).
2. Runs `eval.sh` on the baseline commit, records `state/best.json`.
3. Resets `target_repo/` to the best commit and asks the worker to make one improvement.
4. Scores the change; keeps it only if RMSE improved.

**Check the generated `eval.sh`** before continuing:

```bash
cat eval.sh
./eval.sh target_repo   # should print {"score":...,"higher_is_better":...,"summary":...} on the last line
```

### Subsequent runs

```bash
python3 harness.py loop 5    # run 5 more iterations
```

---

## 8. Inspect outcomes

```bash
cat state/best.json           # current best score + commit SHA in target_repo
cat state/history.jsonl       # one JSON line per iteration
ls runs/                      # per-iteration dir: diff, eval output, result.json

python3 orchestrator/run.sh status   # human-readable best + recent history
```

### Eval contract reminder

`eval.sh` must print a single JSON object as its **last stdout line**:

```json
{"score": 0.42, "higher_is_better": false, "summary": "RMSE of cubic fit"}
```

---

## 9. Demo score trajectory

Running `python3 harness.py loop 5` on `Meta2096/cubic-polyfit` produced:

| Iteration | RMSE | Change kept? | What the worker did |
|-----------|------|-------------|---------------------|
| baseline  | 0.6002 | — | `np.polyfit(x, y, deg=3)` — pure cubic |
| 1 (eval error) | — | no | eval.sh produced no stdout (harness reverted) |
| 2 | **0.1668** | yes | Added `sin(x)` basis column to `np.linalg.lstsq` design matrix |
| 3 | **~1e-13** | yes | Also added `sin(2.5x)` — the exact second harmonic in the true function |
| 4 | ~1e-13 | no | Could not improve further; harness correctly reverted |
| 5 | ~1e-13 | no | Same — score at machine epsilon |

The worker converged in 2 kept changes (72% reduction, then effectively zero) by
discovering the exact functional form of the target signal through feature engineering,
guided by the `knowledge_base/directions.md` hints. The score-gated keep/revert loop
then correctly flat-lined rather than thrashing.

---

## Harness corrections made during this demo

These are bugs/gaps fixed in `harness.py` during this run. They should be
committed back to the harness repo (not just left as local changes):

1. **`dt.UTC` → `dt.timezone.utc`** — `datetime.UTC` was added in Python 3.11;
   the harness was crashing on Python 3.10 with `AttributeError: module 'datetime'
   has no attribute 'UTC'`. Fixed in `run_iteration` and `ensure_baseline`.

2. **Agent model fallback for free-only provider keys** — `render_runtime_config`
   now also pins the `title`, `summarizer`, and `task` internal agents to the
   resolved open model. Without this, opencode falls back to
   `anthropic/claude-haiku-4.5` via OpenRouter for these background agents, which
   fails (HTTP 401/402) when only free-tier keys are configured. The `kb-researcher`
   model resolution was similarly extended to walk the full model chain rather than
   falling back to the unauthenticated OpenCode Zen open model.
