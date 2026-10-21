"""Tune the CV-selected model on training data; use held-out test only for final report.

This is a second-stage, exploratory tuning run. The test set is never passed to
GridSearchCV. Because the model/feature set was chosen in the first CV stage,
the tuning CV score is exploratory; report the untouched test score separately.
"""
from __future__ import annotations
import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.metrics import classification_report
from model_research import (
    DATA_PATH, RESULTS_DIR, FINAL_DIR, FEATURE_SETS, MODEL_LABELS,
    load_dataset, split_dataset, make_estimator, fit_estimator,
    evaluate_predictions, save_classification_details, SEED, N_FOLDS,
)

def main():
    selection_path = RESULTS_DIR / "selected_candidate.json"
    if not selection_path.exists():
        raise SystemExit("Run all four training scripts and src/compare_models.py first.")
    selected = json.loads(selection_path.read_text(encoding="utf-8"))
    model_name = selected["model"]
    feature_set = selected["feature_set"]
    features = FEATURE_SETS[feature_set]
    data = load_dataset(DATA_PATH)
    train, test = split_dataset(data)
    X_train, y_train = train[features].to_numpy(float), train["label"].to_numpy(int)
    X_test, y_test = test[features].to_numpy(float), test["label"].to_numpy(int)

    estimator = make_estimator(model_name)
    if model_name == "logistic_regression":
        grid = {"classifier__C": [0.1, 1.0, 10.0]}
    elif model_name == "random_forest":
        grid = {
            "n_estimators": [300, 500],
            "max_depth": [None, 8, 16],
            "min_samples_leaf": [1, 3],
        }
    elif model_name == "linear_svm":
        grid = {"classifier__C": [0.1, 1.0, 10.0]}
    elif model_name == "xgboost":
        grid = {
            "n_estimators": [200, 300, 500],
            "max_depth": [3, 4, 5],
            "learning_rate": [0.03, 0.1],
            "min_child_weight": [1, 3],
        }
    else:
        raise ValueError(f"Unsupported selected model: {model_name}")

    # Fit weights only on each fold's training labels for XGBoost. sklearn's
    # generic GridSearchCV cannot pass fold-specific sample weights cleanly;
    # use an explicit fold loop for XGBoost below.
    folds = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    if model_name == "xgboost":
        from sklearn.base import clone
        from sklearn.model_selection import ParameterGrid
        from sklearn.metrics import f1_score
        from sklearn.utils.class_weight import compute_sample_weight
        rows = []
        for params in ParameterGrid(grid):
            fold_scores = []
            for fit_idx, val_idx in folds.split(X_train, y_train):
                candidate = make_estimator(model_name).set_params(**params)
                candidate.fit(
                    X_train[fit_idx], y_train[fit_idx],
                    sample_weight=compute_sample_weight("balanced", y_train[fit_idx]),
                )
                pred = candidate.predict(X_train[val_idx])
                fold_scores.append(f1_score(y_train[val_idx], pred, average="macro", zero_division=0))
            rows.append({"params": params, "mean_cv_macro_f1": float(sum(fold_scores)/len(fold_scores)),
                         "std_cv_macro_f1": float(pd.Series(fold_scores).std(ddof=1))})
        tuning = pd.DataFrame(rows).sort_values("mean_cv_macro_f1", ascending=False)
        best_params = tuning.iloc[0]["params"]
        best_score = float(tuning.iloc[0]["mean_cv_macro_f1"])
        best_estimator = make_estimator(model_name).set_params(**best_params)
        fit_estimator(best_estimator, X_train, y_train, model_name)
        tuning.to_json(RESULTS_DIR / "tuning_results.json", orient="records", indent=2)
    else:
        search = GridSearchCV(
            estimator, grid, scoring="f1_macro", cv=folds, n_jobs=-1,
            refit=True, return_train_score=False,
        )
        search.fit(X_train, y_train)
        best_estimator, best_params, best_score = search.best_estimator_, search.best_params_, float(search.best_score_)
        pd.DataFrame(search.cv_results_).to_csv(RESULTS_DIR / "tuning_results.csv", index=False)

    pred = best_estimator.predict(X_test)
    test_metrics = evaluate_predictions(y_test, pred)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    artifact = FINAL_DIR / "tuned_research_candidate.joblib"
    joblib.dump(best_estimator, artifact)
    metadata = {
        **selected, "tuning": {"best_params": best_params, "cv_macro_f1": best_score},
        "held_out_test_metrics": test_metrics,
        "feature_columns": features,
        "label_mapping": {"Normal": 0, "Elevated": 1, "Stage 1": 2, "Stage 2": 3},
        "artifact": str(artifact.relative_to(Path(__file__).resolve().parents[1])),
        "note": "Experimental research model; not clinically validated or a diagnosis.",
    }
    (FINAL_DIR / "tuned_research_candidate.metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str) + "\n", encoding="utf-8"
    )
    save_classification_details(best_estimator, y_test, pred, feature_set, model_name, prefix="tuned_candidate")
    (RESULTS_DIR / "tuned_test_metrics.json").write_text(
        json.dumps(test_metrics, indent=2) + "\n", encoding="utf-8"
    )
    print("Selected baseline:", MODEL_LABELS[model_name], "|", selected["feature_set_label"])
    print("Best tuning parameters:", best_params)
    print("Tuning CV macro-F1:", round(best_score, 4))
    print("Held-out test metrics:", json.dumps(test_metrics, indent=2))
    print("Saved research candidate:", artifact)

if __name__ == "__main__":
    main()
