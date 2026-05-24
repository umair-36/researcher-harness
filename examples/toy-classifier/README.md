# toy-classifier example

A self-contained example for researcher-harness. Uses scikit-learn's Wine
dataset — no downloads, no GPU, runs in a few seconds per iteration.

## What it optimises

5-fold cross-validated accuracy of a scikit-learn classifier on the Wine
dataset. The baseline (shallow Decision Tree) scores around 0.76; a Random
Forest or SVM can reach ~0.98.

## Prerequisites

```bash
pip install scikit-learn numpy
```

## Quick start

Copy the example files into your harness checkout, then run normally:

```bash
cp -r examples/toy-classifier/target     target
cp -r examples/toy-classifier/eval       eval
cp -r examples/toy-classifier/paper      paper
cp -r examples/toy-classifier/directions directions
./scripts/run_once.sh
```

Or use the automated test script, which runs everything with a local mock
agent (no OpenCode or API key required):

```bash
./scripts/test_harness.sh
```

## Files

| Path | Purpose |
|------|---------|
| `target/repo/train.py` | Trains a classifier, prints JSON score on last line |
| `eval/run_eval.sh` | Runs `train.py` — satisfies the harness eval contract |
| `paper/overview.md` | Task description and baseline notes |
| `directions/ideas.md` | Hints for the agent |
