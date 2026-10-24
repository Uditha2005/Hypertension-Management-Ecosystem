"""Audit whether a suggestion-ranking CSV is ready for a grouped ML experiment.

This utility only audits supplied labels; it does not create labels or train a model.
It is safe to run on the blank training schema included with the project.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REQUIRED = {
    "participant_id", "meal_context_id", "candidate_suggestion_id", "candidate_type",
    "eligible_after_safety_filter", "label_source", "expert_relevance_label",
    "constraint_proxy_label", "review_status", "evidence_source_ids",
}
NUMERIC_FEATURES = {
    "vegetable_gap", "legume_gap", "sodium_excess_ratio", "potassium_precaution",
    "grapefruit_precaution", "food_group_fit", "preference_match", "evidence_strength",
}


def truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.casefold().isin({"1", "true", "yes"})


def audit(path: Path) -> dict:
    df = pd.read_csv(path)
    missing_columns = sorted((REQUIRED | NUMERIC_FEATURES) - set(df.columns))
    report: dict = {
        "input": str(path),
        "status": "not_ready",
        "row_count": int(len(df)),
        "missing_required_columns": missing_columns,
    }
    if missing_columns:
        report["reason"] = "Required schema columns are missing."
        return report

    eligible = df[truthy(df["eligible_after_safety_filter"])].copy()
    expert = eligible[
        eligible["label_source"].astype(str).str.casefold().eq("expert")
        & pd.to_numeric(eligible["expert_relevance_label"], errors="coerce").notna()
    ].copy()
    proxy = eligible[pd.to_numeric(eligible["constraint_proxy_label"], errors="coerce").notna()].copy()
    participant_context = (
        eligible["participant_id"].astype(str) + "::" + eligible["meal_context_id"].astype(str)
    )
    expert_context = expert["participant_id"].astype(str) + "::" + expert["meal_context_id"].astype(str)
    expert_group_sizes = expert.assign(_context=expert_context).groupby("_context").size()
    feature_missing = {
        column: int(pd.to_numeric(eligible[column], errors="coerce").isna().sum())
        for column in sorted(NUMERIC_FEATURES)
    }
    report.update({
        "eligible_rows": int(len(eligible)),
        "eligible_participants": int(eligible["participant_id"].nunique()),
        "eligible_meal_contexts": int(participant_context.nunique()),
        "eligible_candidates_with_proxy_label": int(len(proxy)),
        "eligible_candidates_with_expert_label": int(len(expert)),
        "expert_label_participants": int(expert["participant_id"].nunique()),
        "expert_label_contexts": int(expert_context.nunique()),
        "expert_contexts_with_multiple_candidates": int((expert_group_sizes >= 2).sum()),
        "expert_label_distribution": {
            str(k): int(v) for k, v in pd.to_numeric(expert["expert_relevance_label"], errors="coerce").value_counts(dropna=True).sort_index().items()
        },
        "numeric_feature_missing_counts_in_eligible_rows": feature_missing,
        "training_readiness": {
            "minimum_prototype_rows_met": bool(len(expert) >= 30),
            "minimum_participants_met": bool(expert["participant_id"].nunique() >= 5),
            "minimum_contexts_met": bool(expert_context.nunique() >= 10),
            "ranking_contexts_met": bool((expert_group_sizes >= 2).any()),
        },
        "notes": [
            "Proxy labels are not expert judgements and are excluded from the default training path.",
            "At least two expert-labelled candidates per context are needed to calculate meaningful within-context ranking metrics.",
            "Participant IDs must be pseudonymous and stable so group-separated train/validation/test splits are possible.",
            "Evidence source IDs should point to versioned, reviewable sources; a blank source is not evidence.",
        ],
    })
    ready = all(report["training_readiness"].values())
    report["status"] = "expert_label_data_ready_for_prototype_evaluation" if ready else "not_ready"
    if not ready:
        report["reason"] = "The current file does not meet all minimum expert-labelled ranking experiment requirements."
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="CSV using the ranking training schema")
    parser.add_argument("--output", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()
    if not args.input.exists():
        parser.error(f"input file does not exist: {args.input}")
    report = audit(args.input)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] != "not_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
