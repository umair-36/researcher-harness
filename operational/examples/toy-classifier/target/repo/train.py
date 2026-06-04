#!/usr/bin/env python3
"""Toy-classifier baseline for researcher-harness.

Trains a classifier on the scikit-learn Wine dataset and prints the harness
eval JSON (5-fold cross-validated accuracy) on the last stdout line.

Baseline: a shallow Decision Tree (max_depth=2) scores ~0.76. The agent is
expected to swap in a stronger model/pipeline (see directions/ideas.md).
"""
import json

from sklearn.datasets import load_wine
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeClassifier

X, y = load_wine(return_X_y=True)

clf = DecisionTreeClassifier(max_depth=2, random_state=42)
scores = cross_val_score(clf, X, y, cv=5)

print(json.dumps({
    "score": round(float(scores.mean()), 6),
    "higher_is_better": True,
    "summary": "5-fold CV accuracy on Wine",
}))
