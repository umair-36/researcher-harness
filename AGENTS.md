# researcher-harness agent instructions

You are operating inside `researcher-harness`, an autonomous improvement loop.

## Important paths

- Code to modify: `target_repo/`
- Research material: `knowledge_base/` (see `knowledge_base/AGENTS.md`). Small notes are
  inlined in your prompt; large material (papers, PDFs, long notes) is listed in a manifest —
  delegate to the `kb-researcher` subagent (by name or `@kb-researcher`) to extract specific
  facts rather than reading those files into your own context.
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
7. For detail from a large knowledge_base file, ask `kb-researcher` a specific question and use
   its distilled answer; read large files directly only as a fallback, and only the parts you need.
