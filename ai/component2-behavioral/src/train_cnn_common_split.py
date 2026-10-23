
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR / "data" / "processed" / "temporal"
    / "temporal_dataset.npz"
)

SPLIT_FILE = (
    BASE_DIR / "data" / "processed" / "results"
    / "common_split_v2.npz"
)

MODEL_DIR = BASE_DIR / "models"
RESULT_DIR = BASE_DIR / "data" / "processed" / "results"

WINDOW_SIZE = 30
NUM_JOINTS = 17
INPUT_FEATURES = 3

BATCH_SIZE = 32
EPOCHS = 40
LEARNING_RATE = 0.001
SEED = 42


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ============================================================
# SEQUENCE NAMES
# ============================================================

def normalize_sequence(name):
    """Group camera views belonging to the same sequence."""

    name = str(name)

    for suffix in ("-cam0", "-cam1"):
        if name.endswith(suffix):
            return name[:-len(suffix)]

    return name


# ============================================================
# COORDINATE NORMALIZATION
# ============================================================

def normalize_coordinates(X_train, X_test):
    """Fit coordinate statistics on training data only."""

    X_train = X_train.copy()
    X_test = X_test.copy()

    visible_train = X_train[:, :, :, 2] > 0

    means = np.zeros(2, dtype=np.float32)
    stds = np.ones(2, dtype=np.float32)

    for feature in (0, 1):
        values = X_train[:, :, :, feature][visible_train]

        if values.size:
            means[feature] = values.mean()
            stds[feature] = values.std() + 1e-6

    for array in (X_train, X_test):
        visible = array[:, :, :, 2] > 0

        for feature in (0, 1):
            values = array[:, :, :, feature]

            values[visible] = (
                values[visible] - means[feature]
            ) / stds[feature]

            values[~visible] = 0.0

    return X_train, X_test, means, stds


# ============================================================
# 1D CNN MODEL
# ============================================================

class CNNFallDetector(nn.Module):
    """
    Learn temporal patterns from skeleton sequences.

    Input: batch x 30 frames x 17 joints x 3 features.
    The joints and features are flattened for each frame.
    """

    def __init__(self):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv1d(
                in_channels=NUM_JOINTS * INPUT_FEATURES,
                out_channels=64,
                kernel_size=3,
                padding=1,
            ),
            nn.ReLU(),
            nn.BatchNorm1d(64),

            nn.Conv1d(
                in_channels=64,
                out_channels=128,
                kernel_size=3,
                padding=1,
            ),
            nn.ReLU(),
            nn.BatchNorm1d(128),

            nn.MaxPool1d(kernel_size=2),

            nn.Conv1d(
                in_channels=128,
                out_channels=128,
                kernel_size=3,
                padding=1,
            ),
            nn.ReLU(),

            nn.AdaptiveAvgPool1d(1),
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 2),
        )

    def forward(self, x):
        batch_size = x.size(0)

        # (batch, time, joints, features)
        # -> (batch, 51 features, time)
        x = x.reshape(
            batch_size,
            WINDOW_SIZE,
            NUM_JOINTS * INPUT_FEATURES,
        )

        x = x.transpose(1, 2)

        x = self.features(x)

        return self.classifier(x)


# ============================================================
# MAIN
# ============================================================

def main():
    set_seed(SEED)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Temporal dataset not found: {DATA_FILE}"
        )

    
    if not SPLIT_FILE.exists():
        raise FileNotFoundError(
            f"Shared split file not found: {SPLIT_FILE}"
        )

    # Load temporal dataset.
    with np.load(DATA_FILE, allow_pickle=False) as data:
        X = data["X"].astype(np.float32)
        y = data["y"].astype(np.int64)
        groups = data["groups"].astype(str)

    # Load the new shared recording-level split.
    with np.load(SPLIT_FILE, allow_pickle=False) as data:
        train_sequences = {
            normalize_sequence(s)
            for s in data["train_sequences"].astype(str)
        }
        test_sequences = {
            normalize_sequence(s)
            for s in data["test_sequences"].astype(str)
        }


    expected_shape = (
        WINDOW_SIZE,
        NUM_JOINTS,
        INPUT_FEATURES,
    )

    if X.ndim != 4 or X.shape[1:] != expected_shape:
        raise ValueError(
            f"Unexpected dataset shape: {X.shape}"
        )

    if not (len(X) == len(y) == len(groups)):
        raise ValueError(
            "X, y and groups have different lengths."
        )

    normalized_groups = np.array(
        [normalize_sequence(group) for group in groups]
    )

    train_mask = np.isin(
        normalized_groups,
        list(train_sequences),
    )
    test_mask = np.isin(
        normalized_groups,
        list(test_sequences),
    )

    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise ValueError("Train/test split is empty.")

    train_groups = set(normalized_groups[train_idx])
    actual_test_groups = set(normalized_groups[test_idx])

    
    if not train_groups.isdisjoint(actual_test_groups):
        raise ValueError("Sequence leakage detected between train and test.")

    missing_train = train_sequences - train_groups
    if missing_train:
        raise ValueError(
            f"Training sequences missing from dataset: {sorted(missing_train)}"
        )

    missing_test = test_sequences - actual_test_groups
    if missing_test:
        raise ValueError(
            f"Test sequences missing from dataset: {sorted(missing_test)}"
        )


    if not train_groups.isdisjoint(actual_test_groups):
        raise ValueError(
            "Sequence leakage detected between train and test."
        )

    missing = test_sequences - actual_test_groups

    if missing:
        raise ValueError(
            f"Test sequences missing from dataset: {sorted(missing)}"
        )

    X_train = X[train_idx].copy()
    X_test = X[test_idx].copy()

    y_train = y[train_idx]
    y_test = y[test_idx]

    # Use training-only normalization.
    X_train, X_test, coord_means, coord_stds = (
        normalize_coordinates(X_train, X_test)
    )

    class_counts = np.bincount(y_train, minlength=2)

    class_weights = len(y_train) / (
        2.0 * np.maximum(class_counts, 1)
    )

    train_dataset = TensorDataset(
        torch.from_numpy(X_train),
        torch.from_numpy(y_train),
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    model = CNNFallDetector().to(device)

    weights = torch.tensor(
        class_weights,
        dtype=torch.float32,
        device=device,
    )

    criterion = nn.CrossEntropyLoss(weight=weights)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=1e-4,
    )

    print("=" * 60)
    print("1D CNN COMMON-SPLIT TRAINING")
    print("=" * 60)

    print("Device:", device)
    print("Total windows:", len(X))
    print("Training windows:", len(train_idx))
    print("Testing windows:", len(test_idx))
    print("Training sequences:", len(train_groups))
    print("Testing sequences:", len(actual_test_groups))
    print("Train class counts [normal, fall]:", class_counts)
    print(
        "Test class counts [normal, fall]:",
        np.bincount(y_test, minlength=2),
    )
    print("Coordinate means [x, y]:", coord_means)
    print("Coordinate stds [x, y]:", coord_stds)

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    training_start = time.perf_counter()

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0

        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()

            logits = model(batch_x)
            loss = criterion(logits, batch_y)

            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(batch_y)

        if (epoch + 1) % 5 == 0 or epoch == 0:
            average_loss = total_loss / len(train_dataset)

            print(
                f"Epoch {epoch + 1:02d}/{EPOCHS} "
                f"| Loss: {average_loss:.4f}"
            )

    training_seconds = time.perf_counter() - training_start

    # --------------------------------------------------------
    # EVALUATE
    # --------------------------------------------------------

    model.eval()
    test_tensor = torch.from_numpy(X_test).to(device)

    if device.type == "cuda":
        torch.cuda.synchronize()

    inference_start = time.perf_counter()

    with torch.no_grad():
        logits = model(test_tensor)
        predictions = logits.argmax(dim=1).cpu().numpy()

    if device.type == "cuda":
        torch.cuda.synchronize()

    inference_seconds = time.perf_counter() - inference_start

    accuracy = accuracy_score(y_test, predictions)

    precision = precision_score(
        y_test, predictions, zero_division=0
    )

    recall = recall_score(
        y_test, predictions, zero_division=0
    )

    f1 = f1_score(
        y_test, predictions, zero_division=0
    )

    cm = confusion_matrix(
        y_test,
        predictions,
        labels=[0, 1],
    )

    print("\n" + "=" * 60)
    print("1D CNN TEST RESULTS")
    print("=" * 60)

    print(f"Accuracy:       {accuracy:.4f}")
    print(f"Fall precision: {precision:.4f}")
    print(f"Fall recall:    {recall:.4f}")
    print(f"Fall F1-score:  {f1:.4f}")
    print(f"Training time:  {training_seconds:.2f} seconds")
    print(f"Inference time: {inference_seconds:.4f} seconds")

    print("\nClassification report:")

    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["Normal", "Fall"],
            zero_division=0,
        )
    )

    print("Confusion matrix [normal, fall]:")
    print(cm)

    # --------------------------------------------------------
    # SAVE MODEL AND RESULTS
    # --------------------------------------------------------

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = (
        MODEL_DIR / "cnn_fall_detection_common_split.pt"
    )

    result_path = (
        RESULT_DIR / "cnn_common_split_results.npz"
    )

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "window_size": WINDOW_SIZE,
            "num_joints": NUM_JOINTS,
            "input_features": INPUT_FEATURES,
            "class_names": ["normal", "fall"],
            "coordinate_means": coord_means,
            "coordinate_stds": coord_stds,
            "test_sequences": sorted(actual_test_groups),
            "seed": SEED,
        },
        model_path,
    )

    np.savez_compressed(
        result_path,
        y_true=y_test,
        y_pred=predictions,
        confusion_matrix=cm,
        test_groups=groups[test_idx],
        normalized_test_groups=normalized_groups[test_idx],
        train_groups=groups[train_idx],
        accuracy=np.array(accuracy),
        precision=np.array(precision),
        recall=np.array(recall),
        f1=np.array(f1),
        training_seconds=np.array(training_seconds),
        inference_seconds=np.array(inference_seconds),
        seed=np.array(SEED),
    )

    print("\nSaved model:", model_path)
    print("Saved evaluation:", result_path)
    print("\n1D CNN training and evaluation complete.")


if __name__ == "__main__":
    main()
