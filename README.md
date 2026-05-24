# researcher-harness

A minimal agentic research loop around an existing code repository.

The target code goes here:

```text
target/repo/
```

The human direction material go here:

```text
basis/
directions/
```

The harness is deliberately boring: OpenCode proposes and edits code, `eval/run_eval.sh` scores it, the harness records the result, keeps improvements, and reverts failures.

## Layout

```text
research-harness/
  AGENTS.md
  README.md
  opencode.jsonc
  .env.example

  basis/                 # put the basis text, notes, or links here
    README.md

  directions/            # optional human-written research directions
    README.md

  target/
    README.md
    repo/                # clone/copy the open-source code here

  eval/
    run_eval.sh          # user-provided eval, or generated on first run

  scripts/
    setup.sh
    run_once.sh
    loop.sh
    harness.py

  state/                 # machine-readable cumulative memory
    .gitkeep

  runs/                  # per-iteration logs, diffs, eval output
    .gitkeep
```

## Eval contract

`eval/run_eval.sh` receives the target repo path as its first argument:

```bash
./eval/run_eval.sh target/repo
```

It must print a single JSON object on its last stdout line:

```json
{"score": 0.123, "higher_is_better": false, "summary": "validation loss"}
```

Use `higher_is_better: true` for accuracy, pass rate, reward, etc. Use `false` for loss, error, runtime, etc.

## Setup

```bash
cp .env.example .env
# edit .env and set NVIDIA_API_KEY or choose another OPENCODE_MODEL

./scripts/setup.sh
```

Install/authenticate OpenCode if needed:

```bash
curl -fsSL https://opencode.ai/install | bash
opencode auth login --provider nvidia
```

Then put the target code in `target/repo/`:

```bash
rm -rf target/repo
git clone <paper-code-repo-url> target/repo
```

Put the base paper in `paper/`, for example:

```bash
cp ~/Downloads/paper.pdf paper/
```

Add optional direction files:

```bash
cat > directions/ideas.md <<'EOF'
Try to improve evaluation score without increasing inference time by more than 10%.
Prefer small, easily reversible changes.
EOF
```

Provide `eval/run_eval.sh`, or leave the stub and let the first OpenCode run attempt to create one from the paper and target repo.

## Usage

Run one iteration:

```bash
./scripts/run_once.sh
```

Run many iterations:

```bash
./scripts/loop.sh 20
```

Inspect outcomes:

```bash
cat state/history.jsonl
cat state/best.json
ls runs/
```

## Model configuration

Default `.env.example` uses:

```bash
OPENCODE_MODEL=nvidia/deepseek-ai/deepseek-v4-pro
NVIDIA_API_KEY=nvapi-...
```

If that model/tool-call path is unstable for your account/provider state, change only `OPENCODE_MODEL` and the relevant provider key. The harness logic does not depend on the model.

## Safety boundary

Autonomous coding requires shell/edit permissions. This repo assumes you run it in a disposable working tree or container. Keep secrets out of `target/repo`, `paper`, and `directions`.
