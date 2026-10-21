"""Merge saved per-model results and select the candidate by CV macro-F1.

This script does not train models. Run each train_*.py script first.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from model_research import RESULTS_DIR, MODEL_NAMES, MODEL_LABELS, FEATURE_SET_LABELS

def main():
    cv_paths = [RESULTS_DIR / f"{name}_cv.csv" for name in MODEL_NAMES]
    test_paths = [RESULTS_DIR / f"{name}_test.csv" for name in MODEL_NAMES]
    missing = [str(path) for path in cv_paths + test_paths if not path.exists()]
    if missing:
        raise SystemExit(
            "Missing model results. Run all four training scripts first:\n- " + "\n- ".join(missing)
        )
    cv = pd.concat([pd.read_csv(p) for p in cv_paths], ignore_index=True)
    test = pd.concat([pd.read_csv(p) for p in test_paths], ignore_index=True)
    cv = cv.sort_values("cv_macro_f1_mean", ascending=False)
    test.to_csv(RESULTS_DIR / "all_models_test_results.csv", index=False)
    cv.to_csv(RESULTS_DIR / "all_models_cv_results.csv", index=False)
    summary = cv[[
        "model_label", "feature_set_label", "cv_macro_f1_mean",
        "cv_macro_f1_std", "cv_fold_scores"
    ]]
    print("Cross-validation comparison (ranked by mean macro-F1):")
    print(summary.to_string(index=False))
    winner = cv.iloc[0]
    selected = {
        "selection_rule": "Highest mean 5-fold CV macro-F1 on the training partition",
        "model": winner["model"],
        "model_label": winner["model_label"],
        "feature_set": winner["feature_set"],
        "feature_set_label": winner["feature_set_label"],
        "cv_macro_f1_mean": float(winner["cv_macro_f1_mean"]),
        "cv_macro_f1_std": float(winner["cv_macro_f1_std"]),
        "test_set_used_for_selection": False,
        "seed": 42,
        "test_size": 0.2,
        "n_folds": 5,
    }
    (RESULTS_DIR / "selected_candidate.json").write_text(
        json.dumps(selected, indent=2) + "\n", encoding="utf-8"
    )
    winner_test = test[
        (test.model == winner["model"]) &
        (test.feature_set == winner["feature_set"]) &
        (test.group == "all_adults")
    ]
    print("\nSelected using CV only:")
    print(json.dumps(selected, indent=2))
    if not winner_test.empty:
        print("\nHeld-out test performance (reported after selection; not used to select):")
        print(winner_test[["accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1"]].to_string(index=False))
    print(f"\nSaved combined results under {RESULTS_DIR}")

if __name__ == "__main__":
    main()
