# Wine Quality Classifier

Classify the UCI Wine dataset using scikit-learn.

## Dataset

`sklearn.datasets.load_wine()` — 178 samples, 13 physicochemical features, 3 cultivar classes.
No external download needed; bundled with scikit-learn.

## Metric

5-fold cross-validated accuracy (higher is better). Reported via the harness JSON contract.

## Baseline

A shallow Decision Tree (`max_depth=2`) achieves roughly 0.76 accuracy.

## Goal

Improve 5-fold CV accuracy as much as possible while keeping the script fast and deterministic
(use `random_state=42` for reproducibility).
