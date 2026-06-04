# researcher-harness agent instructions

You are operating inside `researcher-harness`, an autonomous improvement loop.

## Important paths

- Code to modify: `target_repo/`
- Research material: `knowledge_base/` (see `knowledge_base/AGENTS.md`)
- Evaluation command: `./eval.sh target_repo`
- Prior outcomes: `state/history.jsonl`, `state/best.json`
- Run logs/diffs: `runs/`

## Rules

1. During improvement iterations, edit only `target_repo/`.
2. Treat the harness itself as read-only: `harness.py`, `eval.sh`, `opencode.jsonc`,
   `AGENTS.md`, `state/`, `runs/`, `knowledge_base/`, `setup/`, `orchestrator/`,
   `messaging/`. The one exception is the initial creation of `eval.sh` when the
   harness explicitly asks for it.
3. Make one coherent change per iteration.
4. Run `./eval.sh target_repo` before finishing whenever feasible.
5. Prefer small diffs, simple code, and reversible hypotheses.
6. Base decisions on the knowledge base and prior outcomes.
