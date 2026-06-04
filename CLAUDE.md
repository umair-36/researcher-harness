# CLAUDE.md — operating this harness with Claude Code

This file is read automatically when **Claude Code** is invoked in this repo. It
governs the case the rest of the harness does not: a human running `claude` here
**manually**, with no `harness.py` wrapper around you. Normally `harness.py`
drives a worker (OpenCode) and does all the bookkeeping. Run by hand, *you* are
the worker, so you must reproduce that discipline yourself.

The shared agent rules and knowledge-base guidance apply to you too:

@AGENTS.md
@knowledge_base/AGENTS.md

## What this repo is

`researcher-harness` points an autonomous coding agent at `target_repo/` and
loops on a measurable score. One iteration is deliberately boring:

> reset `target_repo/` to the best commit → make **one** change → `./eval.sh target_repo` → keep it only if the score improved, else revert → record the outcome.

`harness.py` is the canonical implementation of that loop. Read it as the source
of truth; the protocol below mirrors its functions (`reset_to_best`, `run_eval`,
`is_better`, and the keep-or-revert block in `run_iteration`).

## Two ways to operate

**A. Let the harness drive (preferred when OpenCode is configured).** It handles
every mechanic — reset, eval, keep/revert, state — correctly:

```bash
python3 harness.py check        # verify tools + dirs
python3 harness.py run          # one iteration
python3 harness.py loop 20      # many
```

**B. You are the worker (manual iteration).** Use this when OpenCode is not set
up, or the user explicitly wants Claude Code to make the change. Then follow the
single-iteration protocol below **exactly** — the loop's correctness depends on
it. Do not improvise a different flow.

## Single-iteration protocol (Claude Code as the worker)

Run from the repo root. `target_repo/` is its **own** git repo; all commits,
resets, and the SHA in `state/best.json` refer to *that* inner repo, never the
harness repo.

**0 — Orient on past runs.** Read `state/best.json` (current best score +
commit), tail `state/history.jsonl` (what was tried, what improved, what
failed), and skim recent `runs/<run_id>/` (diffs, eval output). Ground your next
move in this history and the knowledge base — **do not repeat a hypothesis that
already failed.**

If `state/best.json` does not exist yet, establish the baseline first: run
`./eval.sh target_repo` on the current `HEAD`, then write `state/best.json` with
`run_id: "baseline"`, the score, `higher_is_better`, `summary`, `commit:
<target_repo HEAD>`, and append a matching `{"event":"baseline", ...}` line to
`state/history.jsonl`. (Running `python3 harness.py check` once first creates
`state/` and `runs/` and configures `target_repo`'s git identity.)

**1 — Start from the right version.** Reset `target_repo/` to the best commit so
every iteration begins from the same known-good base. Never stack a change on an
unevaluated or worse tree.

```bash
commit=$(python3 -c "import json;print(json.load(open('state/best.json'))['commit'])")
git -C target_repo reset --hard "$commit" && git -C target_repo clean -fd
```

**2 — Use the knowledge base.** Use the inlined small notes directly. For
anything large (papers, PDFs, long notes, anything under
`knowledge_base/library/`), delegate a **specific** question to the
`kb-researcher` subagent (already wired at `.claude/agents/kb-researcher.md`) so
the material is read in an isolated context and only distilled findings come
back. Do not read large files into your own context. Treat direction/constraint
files as binding.

**3 — Make one change.** Exactly **one** small, coherent, reversible change, and
**only** under `target_repo/`. Treat the harness as read-only (the sole
exception is creating `eval.sh` if it is still the `TODO_HARNESS_EVAL` stub).

**4 — Evaluate.** Run the scorer and read the **last** stdout line as JSON:

```bash
./eval.sh target_repo   # → {"score": <num>, "higher_is_better": <bool>, "summary": "..."}
```

**5 — Keep or revert (the eval gates everything).** "Better" means
`score > best.score` when `higher_is_better` is true, else `score < best.score`.
Refuse to compare if `higher_is_better` flipped between runs.

- **Improved** → commit in `target_repo` and update the best pointer:
  ```bash
  run_id=$(date -u +%Y%m%dT%H%M%S_%6NZ)
  git -C target_repo add -A
  git -C target_repo commit -m "researcher-harness $run_id: score <score>"
  newcommit=$(git -C target_repo rev-parse HEAD)
  # overwrite state/best.json with: run_id, score, higher_is_better, summary,
  # commit=$newcommit, created_at=<iso8601 UTC>
  ```
- **Not better / eval errored** → revert, keeping the best base intact:
  ```bash
  git -C target_repo reset --hard "$commit" && git -C target_repo clean -fd
  ```

**6 — Record the run (update the data, always — even on no-improvement).**
Append one line to `state/history.jsonl` and write a `runs/<run_id>/` dir, using
the same fields `harness.py` writes so existing tooling
(`orchestrator/run.sh status`) keeps working:

```json
{"event":"iteration","run_id":"<run_id>","score":<num>,"higher_is_better":<bool>,"summary":"<...>","improved":<bool>,"commit":"<target_repo SHA after keep/revert>","eval_error":<null|"...">}
```

At minimum drop `runs/<run_id>/result.json` (the record above) plus the diff and
eval output; mirror `save_diff`/`run_eval` for full parity if useful. Then
report concisely what changed, the score delta, and whether it was kept.

## Non-negotiables

- **One change per iteration**, only under `target_repo/`. Harness files are
  read-only (except first-time `eval.sh` creation).
- **Always start from `state/best.json`'s commit** — that is "the right
  version." Never build on an unevaluated or regressed tree.
- **Never keep a regression.** The `eval.sh` score is the only gate; don't
  compare across a `higher_is_better` flip.
- **Always update the data after a run** — `state/best.json` (on improvement),
  `state/history.jsonl`, and `runs/<run_id>/` — so the next iteration can learn
  from this one.
- **Commits/resets happen in `target_repo/`'s own git repo**, never the harness
  repo. `state/`, `runs/`, and `target_repo/` are git-ignored runtime data here.
- **Don't dump large knowledge-base files into context** — ask `kb-researcher` a
  specific question instead.

## Quick reference

- Loop / state / logs: `harness.py`, `state/best.json`, `state/history.jsonl`, `runs/`
- Scorer contract: `./eval.sh target_repo` → last line `{"score","higher_is_better","summary"}`
- `run_id` format: `date -u +%Y%m%dT%H%M%S_%6NZ` (e.g. `20260604T172300_123456Z`)
- KB extractor: `@kb-researcher` (`.claude/agents/kb-researcher.md`)
- Status from outside: `python3 orchestrator/run.sh status`
