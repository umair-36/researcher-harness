# Demo run: cubic-polyfit (2026-06-05)

A captured, reproducible record of one `researcher-harness` session so the outcome can be
inspected without re-running the loop. See [`RUNBOOK.md`](../../RUNBOOK.md) for the full
setup that produced this.

## Reproduce

`reproduce.sh` automates the entire `RUNBOOK.md` happy path (install OpenCode, configure
the model + env, clone the target, build the venv + deps, seed the knowledge base,
install the captured `eval.sh`, and verify). It is idempotent and safe to re-run. The
loop itself is opt-in behind `--run`, since it hits the model API.

```bash
# Setup only (stops after harness check, prints next steps):
./demo/cubic-polyfit-run/reproduce.sh <OPENROUTER_API_KEY>

# Setup, then run the first iteration:
./demo/cubic-polyfit-run/reproduce.sh <OPENROUTER_API_KEY> --run
```

The key may also be supplied via `$OPENROUTER_API_KEY`; if omitted, the model/key step is
skipped and any existing `.env` is preserved.

## Configuration

| Setting | Value |
|---------|-------|
| Target repo | [`Meta2096/cubic-polyfit`](https://github.com/Meta2096/cubic-polyfit) |
| Worker model | `openrouter/openai/gpt-oss-20b:free` (free tier) |
| Objective | minimize RMSE of the fit (`higher_is_better: false`) |
| Eval | runs `src/cubic_fit.py`, reads RMSE (col 1) from `outputs/metrics.csv` |
| Knowledge base | `base_paper.pdf` + 3 authored notes (`notes.md`, `directions.md`, `background.md`) |

The target script fits a model to `y = sin(x) + 0.1·x² + 0.25·sin(2.5x)` on 101 points
(seed 42). The baseline uses a plain degree-3 `np.polyfit`, which structurally cannot
represent the sinusoidal components — the headroom the worker exploited.

## Score trajectory

| Iteration | RMSE | Kept? | What the worker did |
|-----------|------|:-----:|---------------------|
| baseline | `0.6002` | — | `np.polyfit(x, y, deg=3)` — pure cubic |
| 1 | — | ✗ | eval produced no stdout; harness reverted |
| 2 | **`0.1668`** | ✓ | Added a `sin(x)` basis column → least-squares design matrix |
| 3 | **`1.11e-13`** | ✓ | Also added `sin(2.5x)` — the exact 2nd harmonic of the signal |
| 4 | `1.11e-13` | ✗ | No further improvement; reverted |
| 5 | `4.03e-13` | ✗ | Slightly worse (numerical); reverted |

Net: **RMSE 0.6002 → ~1e-13** (machine epsilon), **R² → 1.0**, in two kept changes. The
worker reconstructed the exact functional form of the target signal via feature
engineering, guided by `knowledge_base/directions.md`. Once the fit was exact, the
score-gated loop correctly stopped keeping changes instead of thrashing.

## Files

| File | What it is |
|------|-----------|
| `history.jsonl` | canonical per-iteration log (one JSON object per line), copied from `state/` |
| `best.json` | final best-state record (score + winning `target_repo` commit SHA) |
| `final-cubic_fit.py` | the winning `src/cubic_fit.py` from the best commit |
| `final-metrics.csv` | `outputs/metrics.csv` at the best commit (RMSE, MAE, R²) |
| `diffs/01-baseline-to-sin-x.diff` | iteration 2 source change (baseline → `sin(x)`) |
| `diffs/02-sin-x-to-sin-2.5x.diff` | iteration 3 source change (`sin(x)` → `sin(2.5x)`) |
| `eval.sh` | the cubic-specific evaluator used in this run (runs `src/cubic_fit.py`, reads RMSE from `outputs/metrics.csv`). The tracked root `eval.sh` is a generic stub; `reproduce.sh` copies this in. |
| `reproduce.sh` | one-shot, idempotent recipe that recreates this run's setup (see **Reproduce** above) |

Diffs are source-only (`src/cubic_fit.py`); the harness's full `runs/<id>/git.diff.patch`
also contains a ~1.3 MB regenerated-PDF binary delta, omitted here as noise. `runs/`,
`state/`, and `target_repo/` are gitignored runtime dirs, which is why these essentials
are copied into this tracked folder.

## Worker commit SHAs (in `target_repo`)

```
3aa1b45  baseline (initial target state)
fe95516  iteration 2 — score 0.1667512008153305
600de38  iteration 3 — score 1.1117858626035331e-13  (best)
```
