"""Controlled Component 3 model comparison and daily-plan model training.

Research target: NHANES BP-associated category, not meal suitability or future BP.
The deployed candidate uses demographics + Day 1 dietary features so the app's
average daily planned intake is closer to the training feature definition than
a two-day mean model would be for a one-day plan.
"""
from __future__ import annotations
import json
from pathlib import Path
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

COMPONENT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = COMPONENT_DIR / "data" / "processed" / "rebuilt" / "nhanes_bp_diet_rebuilt.csv"
RESULT_DIR = COMPONENT_DIR / "results" / "final_training"
MODEL_DIR = COMPONENT_DIR / "models"
MODEL_PATH = MODEL_DIR / "selected_daily_intake.joblib"
METADATA_PATH = MODEL_DIR / "selected_daily_intake.metadata.json"
SEED = 42
HOLDOUT_SEED = 2026
LABEL_MAPPING = {"Normal": 0, "Elevated": 1, "Stage 1": 2, "Stage 2": 3}
APP_FEATURES = ["age", "sex_female", "bmi", "sodium_mg_mean", "potassium_mg_mean",
                "energy_kcal_mean", "sat_fat_g_mean", "na_k_ratio_mean"]
SOURCE_FEATURES = {
    "demographic_only": ["age", "sex_female", "bmi"],
    "demographic_day1": ["age", "sex_female", "bmi", "sodium_mg_day1",
                         "potassium_mg_day1", "energy_kcal_day1", "sat_fat_g_day1",
                         "na_k_ratio_day1"],
    "demographic_2day_mean": ["age", "sex_female", "bmi", "sodium_mg_2day_mean",
                              "potassium_mg_2day_mean", "energy_kcal_2day_mean",
                              "sat_fat_g_2day_mean", "na_k_ratio_2day_mean"],
}
APP_RENAME = {
    "sodium_mg_day1": "sodium_mg_mean",
    "potassium_mg_day1": "potassium_mg_mean",
    "energy_kcal_day1": "energy_kcal_mean",
    "sat_fat_g_day1": "sat_fat_g_mean",
    "na_k_ratio_day1": "na_k_ratio_mean",
    "sodium_mg_2day_mean": "sodium_mg_mean",
    "potassium_mg_2day_mean": "potassium_mg_mean",
    "energy_kcal_2day_mean": "energy_kcal_mean",
    "sat_fat_g_2day_mean": "sat_fat_g_mean",
    "na_k_ratio_2day_mean": "na_k_ratio_mean",
}
MODEL_BUILDERS = {
    "logistic_regression": lambda: Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(class_weight="balanced", max_iter=3000, random_state=SEED)),
    ]),
    "random_forest": lambda: Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
            max_features="sqrt", class_weight="balanced_subsample", random_state=SEED, n_jobs=-1)),
    ]),
    "extra_trees": lambda: Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", ExtraTreesClassifier(n_estimators=300, min_samples_leaf=3,
            max_features="sqrt", class_weight="balanced", random_state=SEED, n_jobs=-1)),
    ]),
    "rbf_svm": lambda: Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", SVC(C=1.0, kernel="rbf", class_weight="balanced", probability=True, random_state=SEED)),
    ]),
}

def run_experiment(data_path: Path = DATA_PATH) -> dict:
    data = pd.read_csv(data_path)
    required = sorted(set(sum(SOURCE_FEATURES.values(), []) + ["bp_category", "age"]))
    missing = sorted(set(required) - set(data.columns))
    if missing:
        raise ValueError(f"Missing required dataset columns: {missing}")
    # Research/application scope is older adults, consistent with the care setting.
    cohort = data.loc[data["age"].between(60, 80)].copy()
    # Use a matched complete-two-day cohort for feature-set comparisons.
    cohort = cohort.dropna(subset=list(set(SOURCE_FEATURES["demographic_2day_mean"]) |
                                      set(SOURCE_FEATURES["demographic_day1"]) | {"bp_category"}))
    cohort["label"] = cohort["bp_category"].map(LABEL_MAPPING)
    cohort = cohort.loc[cohort["label"].notna()].copy()
    cohort["label"] = cohort["label"].astype(int)
    if len(cohort) < 100 or cohort["label"].nunique() != 4:
        raise ValueError("Insufficient complete older-adult records for four-class training.")

    indices = np.arange(len(cohort))
    dev_idx, test_idx = train_test_split(indices, test_size=0.20, random_state=HOLDOUT_SEED,
                                         stratify=cohort["label"])
    dev = cohort.iloc[dev_idx].copy()
    test = cohort.iloc[test_idx].copy()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    result_rows = []
    fitted_cv_scores = {}
    for feature_set, source_cols in SOURCE_FEATURES.items():
        X = dev[source_cols].astype(float).rename(columns=APP_RENAME)
        y = dev["label"]
        for model_name, builder in MODEL_BUILDERS.items():
            model = builder()
            scores = cross_val_score(model, X, y, cv=cv, scoring="f1_macro", n_jobs=1)
            result_rows.append({
                "feature_set": feature_set,
                "model": model_name,
                "cv_macro_f1_mean": float(np.mean(scores)),
                "cv_macro_f1_std": float(np.std(scores, ddof=1)),
                "fold_scores": ";".join(f"{s:.6f}" for s in scores),
                "development_rows": int(len(dev)),
                "holdout_rows": int(len(test)),
            })
            fitted_cv_scores[(feature_set, model_name)] = float(np.mean(scores))

    results = pd.DataFrame(result_rows).sort_values(
        ["feature_set", "cv_macro_f1_mean"], ascending=[True, False])
    # The deployed app needs daily plan inputs; select among Day-1 models only.
    day1_results = results[results.feature_set == "demographic_day1"].sort_values(
        "cv_macro_f1_mean", ascending=False)
    chosen_name = str(day1_results.iloc[0]["model"])
    chosen = MODEL_BUILDERS[chosen_name]()
    x_train = dev[SOURCE_FEATURES["demographic_day1"]].astype(float).rename(columns=APP_RENAME)
    x_test = test[SOURCE_FEATURES["demographic_day1"]].astype(float).rename(columns=APP_RENAME)
    y_train, y_test = dev["label"], test["label"]
    chosen.fit(x_train, y_train)
    pred = chosen.predict(x_test)
    probabilities = chosen.predict_proba(x_test)
    test_macro_f1 = float(f1_score(y_test, pred, average="macro"))
    test_accuracy = float(accuracy_score(y_test, pred))
    report = classification_report(y_test, pred, labels=[0,1,2,3],
        target_names=["Normal","Elevated","Stage 1","Stage 2"], output_dict=True, zero_division=0)
    matrix = confusion_matrix(y_test, pred, labels=[0,1,2,3])

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULT_DIR / "model_comparison.csv", index=False)
    pd.DataFrame(matrix, index=["true_Normal","true_Elevated","true_Stage1","true_Stage2"],
                 columns=["pred_Normal","pred_Elevated","pred_Stage1","pred_Stage2"]).to_csv(
                     RESULT_DIR / "selected_model_confusion_matrix.csv")
    (RESULT_DIR / "selected_model_test_report.json").write_text(json.dumps({
        "selected_model": chosen_name,
        "feature_set": "demographic_day1",
        "test_macro_f1": test_macro_f1,
        "test_accuracy": test_accuracy,
        "classification_report": report,
        "note": "Exploratory holdout: this dataset and split have been examined in prior project experiments; not independent confirmation."
    }, indent=2) + "\n")
    # Save a reproducible artifact fitted on development partition only.
    joblib.dump(chosen, MODEL_PATH, compress=3)
    medians = x_train.median(numeric_only=True).to_dict()
    metadata = {
        "model_name": chosen_name,
        "target": "NHANES BP-associated category based on measured BP; not a meal suitability label",
        "cohort": "Adults aged 60-80 with complete Day 1 and Day 2 dietary features (matched feature-set comparison)",
        "label_mapping": LABEL_MAPPING,
        "feature_columns": APP_FEATURES,
        "source_feature_columns": SOURCE_FEATURES["demographic_day1"],
        "feature_set": "demographic_day1",
        "feature_reference_medians": {k: float(v) for k,v in medians.items()},
        "cv_macro_f1_mean": float(day1_results.iloc[0]["cv_macro_f1_mean"]),
        "cv_macro_f1_std": float(day1_results.iloc[0]["cv_macro_f1_std"]),
        "holdout_macro_f1": test_macro_f1,
        "holdout_accuracy": test_accuracy,
        "development_rows": int(len(dev)),
        "holdout_rows": int(len(test)),
        "total_matched_cohort_rows": int(len(cohort)),
        "split_seed": HOLDOUT_SEED,
        "cv_folds": 5,
        "holdout_caution": "Prior project work has inspected this dataset/split. Treat holdout metrics as exploratory, not pristine confirmatory evidence.",
        "input_alignment": "Application sends mean daily nutrient totals over selected planned days; training uses Day 1 observed 24-hour recall as the daily-intake representation.",
        "limitations": [
            "The target is BP-associated category, not whether a specific meal is suitable.",
            "NHANES observational data do not establish causality or predict future BP changes.",
            "Planned dietary intake is not established as equivalent to observed recall.",
            "Not clinically validated; not a diagnosis or treatment recommendation.",
            "Model probabilities are classifier outputs and are not calibrated clinical risk probabilities."
        ]
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    audit = {
        "dataset_path": str(data_path),
        "cohort_rows": int(len(cohort)),
        "age_min": int(cohort.age.min()),
        "age_max": int(cohort.age.max()),
        "class_counts": {k: int(v) for k,v in cohort.bp_category.value_counts().to_dict().items()},
        "development_rows": int(len(dev)),
        "holdout_rows": int(len(test)),
        "selected_model": chosen_name,
        "selection_rule": "highest 5-fold CV macro-F1 among models using demographic + Day 1 dietary features",
        "holdout_macro_f1": test_macro_f1,
        "holdout_accuracy": test_accuracy,
    }
    (RESULT_DIR / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    # Compact report authored from actual metrics.
    lines = [
        "# Component 3 — Controlled Model Training Experiment",
        "",
        "## Purpose",
        "Compare four classifiers and three feature sets on a matched older-adult NHANES cohort. The production candidate is selected only among daily-intake (Day 1) models to match a one-day planned-intake interface.",
        "",
        "## Dataset and protocol",
        f"- Matched complete cohort, ages 60–80: **{len(cohort)}** participants.",
        f"- Development partition: **{len(dev)}**; stratified holdout: **{len(test)}**.",
        "- Five-fold stratified cross-validation on the development partition; identical folds for every candidate.",
        "- The held-out split has been inspected in earlier project work, so its metrics are exploratory rather than independent confirmation.",
        "- BP measurement variables are not model features; they are only represented by the target label.",
        "",
        "## Cross-validation results",
        "| Feature set | Model | Mean CV macro-F1 | Fold SD |",
        "|---|---|---:|---:|",
    ]
    for row in results.sort_values("cv_macro_f1_mean", ascending=False).itertuples():
        lines.append(f"| {row.feature_set} | {row.model} | {row.cv_macro_f1_mean:.4f} | {row.cv_macro_f1_std:.4f} |")
    lines += [
        "",
        "## Selected daily-intake model",
        f"- Model: **{chosen_name}**",
        f"- Day-1 feature-set mean CV macro-F1: **{float(day1_results.iloc[0]['cv_macro_f1_mean']):.4f}**",
        f"- Exploratory holdout macro-F1: **{test_macro_f1:.4f}**",
        f"- Exploratory holdout accuracy: **{test_accuracy:.4f}**",
        "",
        "## Class-level results",
        "| Category | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    for cat in ["Normal","Elevated","Stage 1","Stage 2"]:
        d=report[cat]
        lines.append(f"| {cat} | {d['precision']:.3f} | {d['recall']:.3f} | {d['f1-score']:.3f} | {int(d['support'])} |")
    lines += [
        "",
        "## Interpretation and limits",
        "The selected model predicts BP-associated categories from age, sex, BMI and daily dietary features. It does not predict meal suitability, prove causation, diagnose hypertension, or estimate future BP changes. Nutrient-reference checks are displayed separately from the model prediction. Because the data are observational and the holdout has prior exposure, all results are exploratory.",
        "",
    ]
    (RESULT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return {"results": results, "chosen": chosen_name, "cv": float(day1_results.iloc[0]["cv_macro_f1_mean"]),
            "test_f1": test_macro_f1, "test_acc": test_accuracy, "cohort": len(cohort)}

if __name__ == "__main__":
    out=run_experiment()
    print(out["results"].to_string(index=False))
    print(f"\nSelected daily model: {out['chosen']} | CV macro-F1={out['cv']:.4f} | holdout macro-F1={out['test_f1']:.4f} | accuracy={out['test_acc']:.4f}")
