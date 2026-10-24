
from pathlib import Path
import random
import time

import numpy as np
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "ai" / "component2-behavioral" / "data" / "processed"
RESULTS_DIR = DATA_DIR / "results"
MODEL_DIR = ROOT / "ai" / "component2-behavioral" / "models"

DATA_FILE = DATA_DIR / "temporal" / "temporal_dataset.npz"
SPLIT_FILE = RESULTS_DIR / "common_split_v2.npz"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def get_sequence_base(sequence_id):
    """Group camera views belonging to the same recording."""
    sequence_id = str(sequence_id)

    for suffix in ("-cam0", "-cam1"):
        if sequence_id.endswith(suffix):
            return sequence_id[:-len(suffix)]

    return sequence_id


def extract_features(X):
    """
    Extract temporal features from skeleton windows.

    Input shape: (windows, frames, joints, 3)
    Channels: x, y, confidence.
    """
    features = []

    for window in X:
        xy = window[:, :, :2]
        confidence = window[:, :, 2]

        # Joint position statistics.
        mean_xy = np.mean(xy, axis=0)
        std_xy = np.std(xy, axis=0)
        min_xy = np.min(xy, axis=0)
        max_xy = np.max(xy, axis=0)
        range_xy = max_xy - min_xy

        # Joint movement between consecutive frames.
        displacement = np.diff(xy, axis=0)
        speed = np.linalg.norm(displacement, axis=2)

        mean_speed = np.mean(speed, axis=0)
        max_speed = np.max(speed, axis=0)
        std_speed = np.std(speed, axis=0)

        # Joint confidence.
        mean_confidence = np.mean(confidence, axis=0)

        # Whole-skeleton movement.
        body_center = np.mean(xy, axis=1)
        center_displacement = np.diff(body_center, axis=0)
        center_speed = np.linalg.norm(center_displacement, axis=1)

        global_features = np.array([
            np.mean(center_speed),
            np.max(center_speed),
            np.std(center_speed),
            np.mean(speed),
            np.max(speed),
            np.std(speed),
        ])

        feature_vector = np.concatenate([
            mean_xy.flatten(),
            std_xy.flatten(),
            min_xy.flatten(),
            max_xy.flatten(),
            range_xy.flatten(),
            mean_speed.flatten(),
            max_speed.flatten(),
            std_speed.flatten(),
            mean_confidence.flatten(),
            global_features,
        ])

        features.append(feature_vector)

    return np.asarray(features, dtype=np.float32)


def main():
    print("=" * 60)
    print("RANDOM FOREST COMMON-SPLIT TRAINING")
    print("=" * 60)

    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_FILE}")

    if not SPLIT_FILE.exists():
        raise FileNotFoundError(f"Shared split file not found: {SPLIT_FILE}")

    # Load temporal dataset.
    with np.load(DATA_FILE, allow_pickle=False) as dataset:
        X = dataset["X"].astype(np.float32)
        y = dataset["y"].astype(np.int64)
        groups = dataset["groups"].astype(str)

    if not (len(X) == len(y) == len(groups)):
        raise ValueError("X, y and groups have different lengths.")

    # Normalize camera-view names to base recording IDs.
    sequence_ids = np.array([
        get_sequence_base(item) for item in groups
    ])

    # Load the shared split used by the CNN.
    with np.load(SPLIT_FILE, allow_pickle=False) as split_data:
        train_sequences = {
            get_sequence_base(item)
            for item in split_data["train_sequences"].astype(str)
        }
        test_sequences = {
            get_sequence_base(item)
            for item in split_data["test_sequences"].astype(str)
        }

    # Validate split integrity.
    if train_sequences & test_sequences:
        raise ValueError(
            "Sequence leakage detected in common_split_v2.npz."
        )

    dataset_sequences = set(sequence_ids)

    missing_train = train_sequences - dataset_sequences
    missing_test = test_sequences - dataset_sequences

    if missing_train:
        raise ValueError(
            f"Training sequences missing from dataset: {sorted(missing_train)}"
        )

    if missing_test:
        raise ValueError(
            f"Test sequences missing from dataset: {sorted(missing_test)}"
        )

    train_mask = np.isin(sequence_ids, list(train_sequences))
    test_mask = np.isin(sequence_ids, list(test_sequences))

    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise ValueError("Train/test split is empty.")

    if np.any(train_mask & test_mask):
        raise ValueError("Train/test window leakage detected.")

    actual_train_groups = set(sequence_ids[train_idx])
    actual_test_groups = set(sequence_ids[test_idx])

    if not actual_train_groups.isdisjoint(actual_test_groups):
        raise ValueError("Recording leakage detected between train and test.")

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        raise ValueError("Both train and test sets must contain normal and fall samples.")

    print("Dataset windows:", len(X))
    print("Training windows:", len(X_train))
    print("Testing windows:", len(X_test))
    print("Training recordings:", len(actual_train_groups))
    print("Testing recordings:", len(actual_test_groups))
    print("Train class counts [normal, fall]:",
          np.bincount(y_train, minlength=2))
    print("Test class counts [normal, fall]:",
          np.bincount(y_test, minlength=2))
    print("Recording leakage: None")

    # Feature extraction using the same recording-level split.
    print("\nExtracting skeleton temporal features...")
    X_train_features = extract_features(X_train)
    X_test_features = extract_features(X_test)

    print("Feature count:", X_train_features.shape[1])

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=SEED,
        n_jobs=-1,
    )

    print("\nTraining Random Forest...")
    start_time = time.perf_counter()
    model.fit(X_train_features, y_train)
    training_time = time.perf_counter() - start_time

    start_time = time.perf_counter()
    y_pred = model.predict(X_test_features)
    inference_time = time.perf_counter() - start_time

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, pos_label=1, zero_division=0)
    recall = recall_score(y_test, y_pred, pos_label=1, zero_division=0)
    f1 = f1_score(y_test, y_pred, pos_label=1, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])

    print("\n" + "=" * 60)
    print("RANDOM FOREST TEST RESULTS")
    print("=" * 60)
    print(f"Accuracy:       {accuracy:.4f}")
    print(f"Fall precision: {precision:.4f}")
    print(f"Fall recall:    {recall:.4f}")
    print(f"Fall F1-score:  {f1:.4f}")
    print(f"Training time:  {training_time:.2f} seconds")
    print(f"Inference time: {inference_time:.4f} seconds")

    print("\nClassification report:")
    print(classification_report(
        y_test,
        y_pred,
        labels=[0, 1],
        target_names=["Normal", "Fall"],
        zero_division=0,
    ))

    print("Confusion matrix [normal, fall]:")
    print(cm)

    # Save the trained model.
    model_path = MODEL_DIR / "rf_fall_detection_common_split.joblib"
    joblib.dump(model, model_path)

    # Save metrics and recording IDs for reproducibility.
    result_path = RESULTS_DIR / "rf_common_split_results.npz"
    np.savez_compressed(
        result_path,
        accuracy=np.array(accuracy),
        fall_precision=np.array(precision),
        fall_recall=np.array(recall),
        fall_f1=np.array(f1),
        training_time=np.array(training_time),
        inference_time=np.array(inference_time),
        confusion_matrix=cm,
        y_true=y_test,
        y_pred=y_pred,
        test_sequences=np.array(sorted(actual_test_groups)),
        test_groups=groups[test_idx],
        normalized_test_groups=sequence_ids[test_idx],
        train_groups=groups[train_idx],
        feature_count=np.array(X_train_features.shape[1]),
        seed=np.array(SEED),
    )

    print(f"\nSaved model: {model_path}")
    print(f"Saved evaluation: {result_path}")
    print("\nRandom Forest training and evaluation complete.")


if __name__ == "__main__":
    main()
