# CLAUDE.md — Claude Code in researcher-harness

`researcher-harness` points an autonomous coding agent at `target_repo/` and loops on a
measurable score from `eval.sh`. Normally `harness.py` drives a worker (OpenCode); run
by hand, *you* can be that worker. `harness.py` is the source of truth for the loop.

## Routing — is this request about running the improvement loop?

**If yes** — the task is to run or continue an iteration: make a scored change to
`target_repo/` and keep-or-revert it by `eval.sh` (cues: "run/continue an iteration",
"iterate", "improve the target", "make the score go up", or you were launched by the
harness/orchestrator) —

→ **Read `ITERATION.md` and follow it exactly before changing anything.** It is the
single-iteration protocol (start from the best commit → one change under `target_repo/`
→ eval-gate keep/revert → update `state/` + `runs/`) and points to the binding rules in
`AGENTS.md` and `knowledge_base/AGENTS.md`. Skipping it corrupts the loop's state and
history. (`ITERATION.md` is referenced by plain path on purpose, so its detail only
enters context when you actually need it.)

**If no** — anything else (editing the harness itself, fixing `harness.py`, answering
questions, docs, setup, config) is an ordinary task. **Proceed normally**, treating the
whole repo as fair game per the user's request. The iteration-only rules do **not**
apply here — in particular, you are *not* limited to editing `target_repo/`.

When genuinely unsure which mode you're in, skim `ITERATION.md` or ask.
