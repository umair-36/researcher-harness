# Improvement Ideas

- Swap the classifier: try RandomForest, GradientBoosting, SVM (RBF kernel), or KNN.
- Add feature scaling with `StandardScaler` in a `Pipeline` — helps distance-based and kernel methods.
- Tune `max_depth`, `n_estimators`, `C`, or `learning_rate`.
- Try feature selection (`SelectKBest`) to reduce noise dimensions.
- Combine a scaler + ensemble in a single `Pipeline` for a clean one-file change.

Keep `random_state=42` and `cv=5` unchanged so scores remain comparable across iterations.
