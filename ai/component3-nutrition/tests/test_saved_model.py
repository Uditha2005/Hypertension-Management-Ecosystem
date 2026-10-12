"""Verify the persisted selected model and its inference metadata."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

xgboost = pytest.importorskip("xgboost")

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from train_selected_model import (  # noqa: E402
    FEATURE_COLUMNS,
    FEATURE_SET_NAME,
    LABEL_MAPPING,
    METADATA_PATH,
    MODEL_PATH,
)


def test_saved_model_loads_with_expected_metadata():
    assert MODEL_PATH.exists(), f"Train the model first: {MODEL_PATH}"
    assert METADATA_PATH.exists(), f"Metadata is missing: {METADATA_PATH}"

    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert metadata["feature_set_name"] == FEATURE_SET_NAME
    assert metadata["feature_columns"] == FEATURE_COLUMNS
    assert metadata["label_mapping"] == LABEL_MAPPING

    model = xgboost.XGBClassifier()
    model.load_model(MODEL_PATH)
    assert model.get_booster().num_features() == len(FEATURE_COLUMNS)
    assert set(model.classes_) == set(LABEL_MAPPING.values())


def test_saved_model_predicts_valid_feature_dataframe():
    assert MODEL_PATH.exists(), f"Train the model first: {MODEL_PATH}"

    model = xgboost.XGBClassifier()
    model.load_model(MODEL_PATH)

    input_data = pd.DataFrame(
        [
            [45, 0, 24.5, 2500, 3500, 2100, 20, 0.7142857],
            [72, 1, 29.0, 1800, 2800, 1700, 18, 0.6428571],
        ],
        columns=FEATURE_COLUMNS,
    )

    predictions = model.predict(input_data)
    probabilities = model.predict_proba(input_data)

    assert len(predictions) == len(input_data)
    assert set(predictions).issubset(set(LABEL_MAPPING.values()))
    assert probabilities.shape == (len(input_data), len(LABEL_MAPPING))
    assert np.isfinite(probabilities).all()
