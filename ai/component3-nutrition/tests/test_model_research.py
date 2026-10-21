from pathlib import Path
import sys

COMPONENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT_DIR / "src"))

from model_research import (  # noqa: E402
    CATEGORIES, FEATURE_SETS, FORBIDDEN_FEATURES, LABEL_MAPPING,
    make_estimator, load_dataset, split_dataset,
)

def test_label_mapping_is_four_classes():
    assert list(LABEL_MAPPING) == CATEGORIES
    assert set(LABEL_MAPPING.values()) == {0, 1, 2, 3}

def test_features_exclude_target_bp_measurements_and_ids():
    all_features = set(sum(FEATURE_SETS.values(), []))
    assert not all_features.intersection(FORBIDDEN_FEATURES)

def test_dataset_has_one_row_per_participant_and_no_missing_predictors():
    data = load_dataset()
    assert data["participant_id"].is_unique
    assert data["label"].notna().all()
    assert not data[sum(FEATURE_SETS.values(), [])].isna().any().any()

def test_split_is_reproducible_and_stratified():
    data = load_dataset()
    train_a, test_a = split_dataset(data)
    train_b, test_b = split_dataset(data)
    assert train_a["participant_id"].tolist() == train_b["participant_id"].tolist()
    assert test_a["participant_id"].tolist() == test_b["participant_id"].tolist()
    assert set(train_a["participant_id"]).isdisjoint(set(test_a["participant_id"]))
    assert len(test_a) == round(len(data) * 0.2)

def test_estimators_can_be_constructed():
    for model_name in ("logistic_regression", "random_forest", "linear_svm", "xgboost"):
        assert make_estimator(model_name) is not None
