"""Shared, reproducible utilities for Component 3 model research.

All models use the same stratified 80/20 split and the same five-fold CV
folds within the training partition. Blood-pressure readings are target
construction fields only and are never predictors.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score,
    precision_score, recall_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC
from sklearn.utils.class_weight import compute_sample_weight

COMPONENT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = COMPONENT_DIR / "data" / "processed" / "nhanes_bp_diet.csv"
RESULTS_DIR = COMPONENT_DIR / "results" / "model_research"
CANDIDATE_DIR = COMPONENT_DIR / "models" / "research_candidates"
FINAL_DIR = COMPONENT_DIR / "models" / "final"

SEED = 42
TEST_SIZE = 0.20
N_FOLDS = 5
OLDER_AGE = 60
CATEGORIES = ["Normal", "Elevated", "Stage 1", "Stage 2"]
LABEL_MAPPING = {label: i for i, label in enumerate(CATEGORIES)}
LABEL_COLUMN = "bp_category"
ID_COLUMN = "participant_id"
FORBIDDEN_FEATURES = {
    "participant_id", "bp_category", "systolic_avg", "diastolic_avg",
    "label", "systolic", "diastolic", "systolic_bp", "diastolic_bp",
}

DEMOGRAPHIC = ["age", "sex_female", "bmi"]
DIET_DAY1 = [
    "sodium_mg_day1", "potassium_mg_day1", "energy_kcal_day1",
    "sat_fat_g_day1", "na_k_ratio_day1",
]
DIET_MULTIDAY = [
    "sodium_mg_mean", "potassium_mg_mean", "energy_kcal_mean",
    "sat_fat_g_mean", "na_k_ratio_mean",
]
FEATURE_SETS = {
    "demographic_only": DEMOGRAPHIC,
    "demographic_day1": DEMOGRAPHIC + DIET_DAY1,
    "demographic_multiday": DEMOGRAPHIC + DIET_MULTIDAY,
}
FEATURE_SET_LABELS = {
    "demographic_only": "Demographic only",
    "demographic_day1": "Demographic + day 1 diet",
    "demographic_multiday": "Demographic + multi-day diet",
}
MODEL_NAMES = [
    "logistic_regression", "random_forest", "linear_svm", "xgboost",
]
MODEL_LABELS = {
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "linear_svm": "Linear SVM",
    "xgboost": "XGBoost",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_dataset(data_path: Path = DATA_PATH) -> pd.DataFrame:
    """Load and validate the prepared dataset without silently imputing data."""
    data = pd.read_csv(data_path)
    required = {ID_COLUMN, LABEL_COLUMN, *sum(FEATURE_SETS.values(), [])}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    if data[ID_COLUMN].duplicated().any():
        raise ValueError("Expected one row per participant; duplicate participant_id found.")
    if data[LABEL_COLUMN].isna().any():
        raise ValueError("Target labels contain missing values.")
    unknown = sorted(set(data[LABEL_COLUMN].astype(str)) - set(CATEGORIES))
    if unknown:
        raise ValueError(f"Unexpected BP category label(s): {unknown}")
    feature_columns = sorted(set(sum(FEATURE_SETS.values(), [])))
    if set(feature_columns) & FORBIDDEN_FEATURES:
        raise AssertionError("A target, identifier, or BP measurement is in the predictor list.")
    if data[feature_columns].isna().any().any():
        missing_counts = data[feature_columns].isna().sum()
        missing_counts = missing_counts[missing_counts > 0].to_dict()
        raise ValueError(
            "Predictor values are missing. Investigate upstream data construction; "
            f"this pipeline does not silently impute: {missing_counts}"
        )
    if not np.isfinite(data[feature_columns].to_numpy(dtype=float)).all():
        raise ValueError("Predictor data contains non-finite numeric values.")
    data = data.copy()
    data["label"] = data[LABEL_COLUMN].map(LABEL_MAPPING).astype(int)
    return data


def split_dataset(data: pd.DataFrame):
    """One deterministic participant-level stratified split shared by all models."""
    train, test = train_test_split(
        data, test_size=TEST_SIZE, random_state=SEED,
        stratify=data["label"],
    )
    return train.copy(), test.copy()


def make_estimator(model_name: str):
    """Return the baseline estimator; preprocessing is inside the estimator."""
    if model_name == "logistic_regression":
        return Pipeline([
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(
                max_iter=3000, class_weight="balanced", random_state=SEED
            )),
        ])
    if model_name == "random_forest":
        return RandomForestClassifier(
            n_estimators=300, class_weight="balanced",
            random_state=SEED, n_jobs=-1,
        )
    if model_name == "linear_svm":
        return Pipeline([
            ("scale", StandardScaler()),
            ("classifier", LinearSVC(
                class_weight="balanced", random_state=SEED, max_iter=10000
            )),
        ])
    if model_name == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise ImportError(
                "XGBoost is required for this experiment. Install component requirements."
            ) from exc
        return XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.1,
            objective="multi:softprob", num_class=4, eval_metric="mlogloss",
            random_state=SEED, n_jobs=1,
        )
    raise ValueError(f"Unknown model name: {model_name}")


def fit_estimator(estimator, X, y, model_name: str):
    """Fit estimator; XGBoost receives balanced sample weights."""
    if model_name == "xgboost":
        estimator.fit(X, y, sample_weight=compute_sample_weight("balanced", y))
    else:
        estimator.fit(X, y)
    return estimator


def evaluate_predictions(y_true, y_pred) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(precision_score(
            y_true, y_pred, average="macro", zero_division=0
        )),
        "macro_recall": float(recall_score(
            y_true, y_pred, average="macro", zero_division=0
        )),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }


def run_model_experiment(model_name: str, data_path: Path = DATA_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run five-fold CV and held-out evaluation for one algorithm × 3 feature sets."""
    data = load_dataset(data_path)
    train, test = split_dataset(data)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    cv_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []
    folds = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)

    for feature_set, features in FEATURE_SETS.items():
        X_train = train[features].to_numpy(dtype=float)
        y_train = train["label"].to_numpy(dtype=int)
        fold_scores = []
        for fold_number, (fit_idx, val_idx) in enumerate(folds.split(X_train, y_train), start=1):
            estimator = make_estimator(model_name)
            fit_estimator(estimator, X_train[fit_idx], y_train[fit_idx], model_name)
            prediction = estimator.predict(X_train[val_idx])
            fold_scores.append(float(f1_score(
                y_train[val_idx], prediction, average="macro", zero_division=0
            )))
        cv_mean = float(np.mean(fold_scores))
        cv_std = float(np.std(fold_scores, ddof=1))
        cv_rows.append({
            "model": model_name, "model_label": MODEL_LABELS[model_name],
            "feature_set": feature_set,
            "feature_set_label": FEATURE_SET_LABELS[feature_set],
            "cv_macro_f1_mean": cv_mean, "cv_macro_f1_std": cv_std,
            "cv_fold_scores": json.dumps(fold_scores),
            "train_rows": len(train), "test_rows": len(test),
            "seed": SEED, "test_size": TEST_SIZE, "n_folds": N_FOLDS,
        })

        # Fit on all training participants only, then evaluate once on the held-out test.
        estimator = make_estimator(model_name)
        fit_estimator(estimator, X_train, y_train, model_name)
        y_test = test["label"].to_numpy(dtype=int)
        test_prediction = estimator.predict(test[features].to_numpy(dtype=float))
        candidate_path = CANDIDATE_DIR / f"{model_name}__{feature_set}.joblib"
        joblib.dump(estimator, candidate_path)

        for group_name, mask in [
            ("all_adults", np.ones(len(test), dtype=bool)),
            ("age_60_plus", test["age"].to_numpy() >= OLDER_AGE),
        ]:
            if not mask.any():
                continue
            test_rows.append({
                "model": model_name, "model_label": MODEL_LABELS[model_name],
                "feature_set": feature_set,
                "feature_set_label": FEATURE_SET_LABELS[feature_set],
                "group": group_name, "n": int(mask.sum()),
                **evaluate_predictions(y_test[mask], test_prediction[mask]),
                "artifact_path": str(candidate_path.relative_to(COMPONENT_DIR)),
            })

    cv_df, test_df = pd.DataFrame(cv_rows), pd.DataFrame(test_rows)
    cv_df.to_csv(RESULTS_DIR / f"{model_name}_cv.csv", index=False)
    test_df.to_csv(RESULTS_DIR / f"{model_name}_test.csv", index=False)
    return cv_df, test_df


def save_classification_details(
    estimator, y_true, y_pred, feature_set: str, model_name: str,
    prefix: str = "selected_candidate",
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = classification_report(
        y_true, y_pred, labels=list(range(len(CATEGORIES))),
        target_names=CATEGORIES, zero_division=0, output_dict=True,
    )
    (RESULTS_DIR / f"{prefix}_classification_report.json").write_text(
        json.dumps({
            "model": model_name, "feature_set": feature_set,
            "labels": CATEGORIES, "report": report,
        }, indent=2) + "\n", encoding="utf-8",
    )
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(CATEGORIES))))
    pd.DataFrame(cm, index=CATEGORIES, columns=CATEGORIES).to_csv(
        RESULTS_DIR / f"{prefix}_confusion_matrix.csv"
    )
