
from pathlib import Path
import random
import time

import numpy as np
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
SPLIT_FILE = RESULTS_DIR / "depth_baseline_results.npz"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def get_sequence_base(sequence_id):
    """Prevent camera-view variants from being treated as separate sequences."""
    sequence_id = str(sequence_id)

    if sequence_id.endswith("-cam0") or sequence_id.endswith("-cam1"):
        return sequence_id.rsplit("-", 1)[0]

    return sequence_id


def extract_features(X):
    """
    Extract temporal features from skeleton windows.

    Input shape: (windows, frames, joints, 3)
    Channels: x, y, confidence.
    """
    features = []

    for window in X:
        xy = window[:, :, :2]  # (frames, joints, x/y)
        confidence = window[:, :, 2]

        # Joint position statistics across the temporal window.
        mean_xy = np.mean(xy, axis=0)
        std_xy = np.std(xy, axis=0)
        min_xy = np.min(xy, axis=0)
        max_xy = np.max(xy, axis=0)
        range_xy = max_xy - min_xy

        # Movement between consecutive frames.
        displacement = np.diff(xy, axis=0)
        speed = np.linalg.norm(displacement, axis=2)

        mean_speed = np.mean(speed, axis=0)
        max_speed = np.max(speed, axis=0)
        std_speed = np.std(speed, axis=0)

        # Confidence statistics for each joint.
        mean_confidence = np.mean(confidence, axis=0)

        # Whole-skeleton movement features.
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

    dataset = np.load(DATA_FILE, allow_pickle=True)
    split_data = np.load(SPLIT_FILE, allow_pickle=True)

    X = dataset["X"]
    y = dataset["y"].astype(np.int64)

    # Dataset sequence IDs.
    sequence_key = next(
        (
            key for key in ("sequence_ids", "sequence_id", "groups", "seq_ids")
            if key in dataset.files
        ),
        None,
    )

    if sequence_key is None:
        raise KeyError(
            "Could not find sequence IDs in temporal_dataset.npz. "
            f"Available keys: {dataset.files}"
        )

    sequence_ids = np.array([
        get_sequence_base(item) for item in dataset[sequence_key]
    ])

    # Find the shared test sequence IDs saved by the baseline split.
    test_key = next(
        (
            key for key in ("test_sequences", "test_sequence_ids", "test_groups")
            if key in split_data.files
        ),
        None,
    )

    if test_key is None:
        raise KeyError(
            "Could not find test sequence IDs in depth_baseline_results.npz. "
            f"Available keys: {split_data.files}"
        )

    test_sequences = {
        get_sequence_base(item) for item in split_data[test_key]
    }

    test_mask = np.isin(sequence_ids, list(test_sequences))
    train_mask = ~test_mask

    if not np.any(test_mask) or not np.any(train_mask):
        raise ValueError("Train/test split is empty. Check the sequence IDs.")

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    print(f"Total windows: {len(X)}")
    print(f"Training windows: {len(X_train)}")
    print(f"Testing windows: {len(X_test)}")
    print(f"Training sequences: {len(set(sequence_ids[train_mask]))}")
    print(f"Testing sequences: {len(set(sequence_ids[test_mask]))}")
    print("Train class counts [normal, fall]:", np.bincount(y_train, minlength=2))
    print("Test class counts [normal, fall]:", np.bincount(y_test, minlength=2))

    # Extract features separately for the same train/test split.
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

    # Save the trained model using joblib.
    import joblib

    model_path = MODEL_DIR / "rf_fall_detection_common_split.joblib"
    joblib.dump(model, model_path)

    result_path = RESULTS_DIR / "rf_common_split_results.npz"
    np.savez(
        result_path,
        accuracy=accuracy,
        fall_precision=precision,
        fall_recall=recall,
        fall_f1=f1,
        training_time=training_time,
        inference_time=inference_time,
        confusion_matrix=cm,
        y_true=y_test,
        y_pred=y_pred,
        test_sequences=np.array(sorted(test_sequences)),
        feature_count=X_train_features.shape[1],
    )

    print(f"\nSaved model: {model_path}")
    print(f"Saved evaluation: {result_path}")
    print("\nRandom Forest training and evaluation complete.")


if __name__ == "__main__":
    main()
