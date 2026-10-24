"""Regression tests for ranking research tooling; no clinical claims are tested here."""
from pathlib import Path
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from audit_training_data import audit  # noqa: E402
from src_train_ranker import ndcg_at_k, rule_baseline_score  # noqa: E402


def test_blank_training_template_is_reported_not_ready():
    template = HERE / "training_examples_template.csv"
    report = audit(template)
    assert report["status"] == "not_ready"
    assert report["eligible_candidates_with_expert_label"] == 0
    assert report["training_readiness"]["minimum_prototype_rows_met"] is False


def test_ndcg_uses_participant_and_context_key_and_skips_single_candidate_contexts():
    frame = pd.DataFrame({
        "participant_id": ["p1", "p1", "p2"],
        "meal_context_id": ["same", "same", "same"],
        "expert_relevance_label": [3, 0, 2],
    })
    score = ndcg_at_k(frame, [0.9, 0.1, 0.5], k=3)
    assert score == 1.0  # p1 context is ranked perfectly; p2 has one candidate and is skipped.


def test_rule_baseline_scores_only_from_available_feature_columns():
    frame = pd.DataFrame({
        "vegetable_gap": [1.0, 0.0],
        "legume_gap": [1.0, 0.0],
        "sodium_excess_ratio": [0.5, 0.0],
        "potassium_precaution": [0.0, 0.0],
        "grapefruit_precaution": [0.0, 0.0],
        "food_group_fit": [1.0, 0.2],
        "preference_match": [1.0, 0.1],
        "evidence_strength": [1.0, 0.2],
        "candidate_type": ["food_group", "general"],
    })
    scores = rule_baseline_score(frame)
    assert len(scores) == 2
    assert scores[0] > scores[1]


def test_interaction_coverage_audit_keeps_unresolved_catalogue_labels_unresolved():
    from audit_interaction_coverage import audit as audit_interactions

    catalogue = HERE / "medication_catalogue_coverage_template.csv"
    registry = HERE.parents[1] / "src" / "medication_food_interactions.json"
    table, report = audit_interactions(catalogue, registry)
    assert report["catalogue_labels"] == 22
    assert report["labels_unresolved"] == 4
    assert report["status"] == "partial_coverage_only"
    unresolved = table[table["candidate_active_ingredient"].eq("")]
    assert unresolved["interpretation"].str.contains("verify packaging/prescription", case=False).all()
    assert table["prescription_confirmation_status"].eq("not_confirmed_by_this_audit").all()


def test_ddid_audit_preserves_rows_and_never_approves_runtime_rule(tmp_path):
    from audit_ddid_export import audit as audit_ddid

    source = tmp_path / "ddid_fixture.csv"
    pd.DataFrame({
        "Drug Name": ["Ramipril", "Unknown medicine"],
        "Food Name": ["Potassium salt substitute", "Grapefruit"],
        "Interaction Type": ["example record", "example record"],
        "Reference": ["https://example.invalid/a", "https://example.invalid/b"],
    }).to_csv(source, index=False)
    candidates, report = audit_ddid(source)
    assert report["rows_total"] == 2
    assert report["rows_matching_supported_or_related_medicine_terms"] == 1
    assert "Food Name" in candidates.columns
    assert candidates.iloc[0]["Food Name"] == "Potassium salt substitute"
    assert candidates.iloc[0]["review_status"] == "unreviewed_candidate_not_for_runtime"
    assert candidates.iloc[0]["runtime_promotion_allowed"] == "no"
    assert report["runtime_rules_added"] == 0
