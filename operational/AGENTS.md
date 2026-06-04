# research-harness agent instructions

You are operating inside `research-harness`.

## Important paths

- Target code to modify: `target/repo/`
- Paper/material: `paper/`
- Human direction material: `directions/`
- Evaluation command: `eval/run_eval.sh target/repo`
- Prior outcomes: `state/history.jsonl`, `state/best.json`
- Run logs/diffs: `runs/`

## Rules

1. During improvement iterations, edit only `target/repo/`.
2. Treat `scripts/`, `state/`, `runs/`, `paper/`, and `directions/` as read-only unless explicitly asked to create the initial eval script.
3. Make one coherent research change per iteration.
4. Run the eval before finishing whenever feasible.
5. Prefer small diffs, simple code, and reversible hypotheses.
6. Base decisions on the paper, direction files, and prior outcomes.
