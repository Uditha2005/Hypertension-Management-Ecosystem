"""Train/evaluate a candidate-suggestion ranker from explicitly labelled data.

This script intentionally refuses to train when there are no eligible labelled
examples. Expert relevance labels are preferred. Proxy labels require an explicit
--allow-proxy-labels flag and must never be reported as expert-validated results.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer

NUMERIC_FEATURES = [
    "vegetable_gap", "legume_gap", "sodium_excess_ratio",
    "potassium_precaution", "grapefruit_precaution", "food_group_fit",
    "preference_match", "evidence_strength",
]
CATEGORICAL_FEATURES = ["candidate_type"]
GROUP_COLUMNS = ["participant_id", "meal_context_id"]


def dcg(relevances: Iterable[float]) -> float:
    values = np.asarray(list(relevances), dtype=float)
    if values.size == 0:
        return 0.0
    gains = np.power(2.0, values) - 1.0
    discounts = np.log2(np.arange(2, values.size + 2))
    return float(np.sum(gains / discounts))


def _context_key(frame: pd.DataFrame) -> pd.Series:
    # Context IDs may only be unique within a participant in user-collected data.
    return frame["participant_id"].astype(str) + "::" + frame["meal_context_id"].astype(str)


def ndcg_at_k(frame: pd.DataFrame, predictions: np.ndarray, k: int = 3) -> float | None:
    """NDCG@k over contexts with at least two candidates and expert labels."""
    work = frame[["participant_id", "meal_context_id", "expert_relevance_label"]].copy()
    work["context_key"] = _context_key(work)
    work["prediction"] = np.asarray(predictions, dtype=float)
    scores: list[float] = []
    for _, group in work.groupby("context_key"):
        if len(group) < 2:
            continue
        actual = group["expert_relevance_label"].to_numpy(dtype=float)
        pred = group["prediction"].to_numpy(dtype=float)
        order = np.argsort(-pred)[:k]
        ideal = np.sort(actual)[::-1][:k]
        denominator = dcg(ideal)
        scores.append(dcg(actual[order]) / denominator if denominator > 0 else 1.0)
    return float(np.mean(scores)) if scores else None


def make_ridge_pipeline() -> Pipeline:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    prep = ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])
    return Pipeline([("features", prep), ("ranker", Ridge(alpha=1.0))])


def rule_baseline_score(frame: pd.DataFrame) -> np.ndarray:
    """Simple transparent score used as a comparator, not as clinical guidance."""
    numeric = frame[NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    candidate = frame["candidate_type"].astype(str).str.casefold()
    type_bonus = candidate.map({
        "food_group": 0.10,
        "nutrient": 0.10,
        "substitution": 0.05,
        "medication_precaution": 0.0,
        "general": -0.10,
    }).fillna(0.0).to_numpy()
    # Evidence and meal fit lead the baseline; it does not override the separate safety filter.
    return (
        0.35 * numeric["evidence_strength"].to_numpy()
        + 0.30 * numeric["food_group_fit"].to_numpy()
        + 0.20 * numeric["preference_match"].to_numpy()
        + 0.10 * numeric["sodium_excess_ratio"].clip(0, 1).to_numpy()
        - 0.15 * numeric["vegetable_gap"].clip(0, 1).to_numpy() * (candidate != "food_group").to_numpy()
        + type_bonus
    )


def make_pipeline() -> Pipeline:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    prep = ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("features", prep),
        ("ranker", RandomForestRegressor(
            n_estimators=300, min_samples_leaf=2, max_features=0.9,
            random_state=42, n_jobs=-1,
        )),
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV of candidate suggestion rows")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-proxy-labels", action="store_true", help="Explicitly allow constraint_proxy_label as the target")
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f"input file does not exist: {args.input}")
    df = pd.read_csv(args.input)
    required = set(GROUP_COLUMNS + NUMERIC_FEATURES + CATEGORICAL_FEATURES + [
        "eligible_after_safety_filter", "label_source", "expert_relevance_label", "constraint_proxy_label"
    ])
    missing = sorted(required - set(df.columns))
    if missing:
        parser.error("missing required columns: " + ", ".join(missing))

    df = df[df["eligible_after_safety_filter"].astype(str).str.casefold().isin({"1", "true", "yes"})].copy()
    if args.allow_proxy_labels:
        df["target"] = pd.to_numeric(df["expert_relevance_label"], errors="coerce")
        proxy_rows = df["target"].isna()
        df.loc[proxy_rows, "target"] = pd.to_numeric(df.loc[proxy_rows, "constraint_proxy_label"], errors="coerce")
        target_kind = "expert_and_explicitly_allowed_proxy_labels"
    else:
        df = df[df["label_source"].astype(str).str.casefold().eq("expert")].copy()
        df["target"] = pd.to_numeric(df["expert_relevance_label"], errors="coerce")
        target_kind = "expert_relevance_labels_only"
    df = df.dropna(subset=["participant_id", "meal_context_id", "candidate_type", "target"])
    if len(df) < 30 or df["participant_id"].nunique() < 5 or df["meal_context_id"].nunique() < 10:
        parser.error(
            f"insufficient labelled data: found {len(df)} eligible rows, "
            f"{df['participant_id'].nunique()} participants and {df['meal_context_id'].nunique()} meal contexts; "
            "need at least 30 rows, 5 participants and 10 meal contexts for this prototype evaluation"
        )
    if (_context_key(df).value_counts() >= 2).sum() == 0:
        parser.error("ranking requires at least some participant meal contexts with two or more candidate suggestions")

    x_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    # Normalize user-authored CSV fields before sklearn sees them. Missing feature values
    # are imputed by each pipeline; invalid numeric strings become missing rather than crashing.
    for column in NUMERIC_FEATURES + ["expert_relevance_label", "constraint_proxy_label"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["target", "participant_id", "meal_context_id", "candidate_type"]).copy()
    # Re-create splits after dropping invalid targets to preserve grouping guarantees.
    if len(df) < 30 or df["participant_id"].nunique() < 5 or df["meal_context_id"].nunique() < 10:
        parser.error("insufficient valid labelled rows after numeric validation; collect more reviewed examples")
    outer = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_val_idx, test_idx = next(outer.split(df, groups=df["participant_id"]))
    train_val = df.iloc[train_val_idx].copy()
    test = df.iloc[test_idx].copy()
    inner = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=43)
    train_idx, val_idx = next(inner.split(train_val, groups=train_val["participant_id"]))
    train = train_val.iloc[train_idx].copy()
    val = train_val.iloc[val_idx].copy()
    if min(train["participant_id"].nunique(), val["participant_id"].nunique(), test["participant_id"].nunique()) < 1:
        parser.error("grouped split produced an empty participant split; collect more participants")

    candidates = {
        "ridge_regression": make_ridge_pipeline(),
        "random_forest": make_pipeline(),
        "extra_trees": Pipeline([
            ("features", make_pipeline().named_steps["features"]),
            ("ranker", ExtraTreesRegressor(n_estimators=300, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=-1)),
        ]),
    }
    x_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    comparison: dict[str, dict[str, float | None]] = {}
    fitted: dict[str, Pipeline] = {}
    for name, candidate_model in candidates.items():
        candidate_model.fit(train[x_cols], train["target"].astype(float))
        val_pred = candidate_model.predict(val[x_cols])
        test_pred = candidate_model.predict(test[x_cols])
        val_expert = val[
            val["label_source"].astype(str).str.casefold().eq("expert")
            & pd.to_numeric(val["expert_relevance_label"], errors="coerce").notna()
        ].copy()
        if len(val_expert):
            val_expert_frame = val_expert.copy()
            val_expert_frame["expert_relevance_label"] = val_expert_frame["target"].astype(float)
            validation_expert_ndcg = ndcg_at_k(val_expert_frame, candidate_model.predict(val_expert[x_cols]))
        else:
            validation_expert_ndcg = None
        test_expert = test[
            test["label_source"].astype(str).str.casefold().eq("expert")
            & pd.to_numeric(test["expert_relevance_label"], errors="coerce").notna()
        ].copy()
        if len(test_expert):
            expert_pred = candidate_model.predict(test_expert[x_cols])
            expert_frame = test_expert.copy()
            expert_frame["expert_relevance_label"] = expert_frame["target"].astype(float)
            model_ndcg = ndcg_at_k(expert_frame, expert_pred)
        else:
            model_ndcg = None
        comparison[name] = {
            "validation_mae": float(mean_absolute_error(val["target"], val_pred)),
            "validation_expert_ndcg_at_3": validation_expert_ndcg,
            "test_mae": float(mean_absolute_error(test["target"], test_pred)),
            "test_expert_ndcg_at_3": model_ndcg,
        }
        fitted[name] = candidate_model

    val_expert = val[
        val["label_source"].astype(str).str.casefold().eq("expert")
        & pd.to_numeric(val["expert_relevance_label"], errors="coerce").notna()
    ].copy()
    test_expert = test[
        test["label_source"].astype(str).str.casefold().eq("expert")
        & pd.to_numeric(test["expert_relevance_label"], errors="coerce").notna()
    ].copy()
    if len(val_expert):
        val_expert_frame = val_expert.copy()
        val_expert_frame["expert_relevance_label"] = val_expert_frame["target"].astype(float)
        baseline_validation_ndcg = ndcg_at_k(val_expert_frame, rule_baseline_score(val_expert_frame))
    else:
        baseline_validation_ndcg = None
    if len(test_expert):
        test_expert_frame = test_expert.copy()
        test_expert_frame["expert_relevance_label"] = test_expert_frame["target"].astype(float)
        baseline_pred = rule_baseline_score(test_expert_frame)
        baseline_ndcg = ndcg_at_k(test_expert_frame, baseline_pred)
    else:
        baseline_ndcg = None
    # Prefer ranking quality when independent expert labels exist in validation. If not,
    # MAE is used only as a proxy experiment criterion and the limitation is reported.
    if any(comparison[name]["validation_expert_ndcg_at_3"] is not None for name in comparison):
        best_name = max(comparison, key=lambda name: (
            comparison[name]["validation_expert_ndcg_at_3"] if comparison[name]["validation_expert_ndcg_at_3"] is not None else -1.0,
            -comparison[name]["validation_mae"],
        ))
        selection_criterion = "validation_expert_ndcg_at_3_then_mae"
    else:
        best_name = min(comparison, key=lambda name: comparison[name]["validation_mae"] if comparison[name]["validation_mae"] is not None else float("inf"))
        selection_criterion = "validation_mae_proxy_only_no_expert_ranking_labels"
    model = fitted[best_name]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "suggestion_ranker.joblib"
    joblib.dump(model, model_path)
    metrics = {
        "status": "trained_research_candidate_not_clinically_validated",
        "target_kind": target_kind,
        "selected_model": best_name,
        "selection_criterion": selection_criterion,
        "n_rows": int(len(df)),
        "n_participants": int(df["participant_id"].nunique()),
        "n_contexts": int(_context_key(df).nunique()),
        "split_rows": {"train": int(len(train)), "validation": int(len(val)), "test": int(len(test))},
        "model_comparison": comparison,
        "rule_baseline_validation_expert_ndcg_at_3": baseline_validation_ndcg,
        "rule_baseline_test_expert_ndcg_at_3": baseline_ndcg,
        "model_path": str(model_path),
        "limitations": [
            "A ranking score is not a medication safety decision.",
            "Proxy-label results are not expert-validated when proxy labels are allowed.",
            "NDCG is computed only on held-out contexts with at least two expert-labelled candidates.",
            "A lower validation MAE does not establish better clinical relevance; compare ranking metrics and expert review before integration.",
            "Independent expert review and comparison with a rule baseline are required before integration.",
        ],
    }
    (args.output_dir / "evaluation.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
