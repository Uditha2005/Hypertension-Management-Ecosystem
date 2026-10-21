"""Authoritative model contract for Component 3 daily-intake inference.

Run ``python src/run_final_training_experiment.py`` to reproduce the controlled
comparison and write the selected artifact. The selected model predicts an
NHANES BP-associated category, not meal suitability or future BP.
"""
from __future__ import annotations
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = COMPONENT_DIR / "data" / "processed" / "rebuilt" / "nhanes_bp_diet_rebuilt.csv"
MODEL_DIR = COMPONENT_DIR / "models"
MODEL_PATH = MODEL_DIR / "selected_daily_intake.joblib"
METADATA_PATH = MODEL_DIR / "selected_daily_intake.metadata.json"
FEATURE_SET_NAME = "Demographics + daily dietary intake (Day 1 training representation)"
FEATURE_COLUMNS = [
    "age", "sex_female", "bmi", "sodium_mg_mean", "potassium_mg_mean",
    "energy_kcal_mean", "sat_fat_g_mean", "na_k_ratio_mean",
]
LABEL_MAPPING = {"Normal": 0, "Elevated": 1, "Stage 1": 2, "Stage 2": 3}

def train_and_save_model(data_path: Path = DATA_PATH):
    """Run the controlled experiment; return selected model and metadata paths."""
    try:
        from run_final_training_experiment import run_experiment
    except ModuleNotFoundError:
        from .run_final_training_experiment import run_experiment
    run_experiment(data_path)
    return MODEL_PATH, METADATA_PATH

if __name__ == "__main__":
    train_and_save_model()
