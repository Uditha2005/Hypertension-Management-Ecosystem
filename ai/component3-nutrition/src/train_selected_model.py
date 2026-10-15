"""Train and save the selected Function 1 XGBoost model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier


COMPONENT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = COMPONENT_DIR / "data" / "processed" / "nhanes_bp_diet.csv"
MODEL_DIR = COMPONENT_DIR / "models"
MODEL_PATH = MODEL_DIR / "selected_xgboost_multiday.json"
METADATA_PATH = MODEL_DIR / "selected_xgboost_multiday.metadata.json"

SEED = 42
TEST_SIZE = 0.2
FEATURE_SET_NAME = "Demographic + multi-day diet"
FEATURE_COLUMNS = [
    "age",
    "sex_female",
    "bmi",
    "sodium_mg_mean",
    "potassium_mg_mean",
    "energy_kcal_mean",
    "sat_fat_g_mean",
    "na_k_ratio_mean",
]
LABEL_MAPPING = {"Normal": 0, "Elevated": 1, "Stage 1": 2, "Stage 2": 3}
ALGORITHM_CONFIGURATION = {
    "name": "XGBoost",
    "parameters": {
        "n_estimators": 300,
        "max_depth": 4,
        "learning_rate": 0.1,
        "eval_metric": "mlogloss",
        "random_state": SEED,
    },
    "sample_weight": "compute_sample_weight('balanced', y_train)",
}


def create_model() -> XGBClassifier:
    """Create the XGBoost estimator with the notebook's configuration."""
    return XGBClassifier(**ALGORITHM_CONFIGURATION["parameters"])


def train_and_save_model(
    data_path: Path = DATA_PATH,
    model_path: Path = MODEL_PATH,
    metadata_path: Path = METADATA_PATH,
) -> tuple[Path, Path]:
    """Fit on the notebook's training split and save the estimator and metadata."""
    data = pd.read_csv(data_path)
    data["label"] = data["bp_category"].map(LABEL_MAPPING)

    if data[FEATURE_COLUMNS + ["label"]].isna().any().any():
        raise ValueError("Selected model columns and labels must not contain missing values")

    train, _ = train_test_split(
        data,
        test_size=TEST_SIZE,
        stratify=data["label"],
        random_state=SEED,
    )

    model = create_model()
    model.fit(
        train[FEATURE_COLUMNS].to_numpy(),
        train["label"].to_numpy(),
        sample_weight=compute_sample_weight("balanced", train["label"].to_numpy()),
    )

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(model_path)

    metadata = {
        "feature_set_name": FEATURE_SET_NAME,
        "feature_columns": FEATURE_COLUMNS,
        "label_mapping": LABEL_MAPPING,
        "algorithm": ALGORITHM_CONFIGURATION,
        "training": {
            "data_path": str(data_path),
            "test_size": TEST_SIZE,
            "random_state": SEED,
            "fit_partition": "train split only; held-out test split was not fitted",
            "training_rows": len(train),
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return model_path, metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    args = parser.parse_args()

    model_path, metadata_path = train_and_save_model(args.data, args.model, args.metadata)
    print(f"Saved model to {model_path}")
    print(f"Saved metadata to {metadata_path}")


if __name__ == "__main__":
    main()
