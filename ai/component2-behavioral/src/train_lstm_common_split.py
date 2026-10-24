
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
# PATHS AND CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "temporal"
    / "temporal_dataset.npz"
)

SPLIT_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "results"
    / "common_split_v2.npz"
)

MODEL_DIR = BASE_DIR / "models"
RESULT_DIR = BASE_DIR / "data" / "processed" / "results"

WINDOW_SIZE = 30
NUM_JOINTS = 17
INPUT_FEATURES = 3

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.30

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
# SEQUENCE NAME NORMALIZATION
# ============================================================

def normalize_sequence(name):
    """Convert fall-06-cam0 and fall-06-cam1 to fall-06."""
    name = str(name)

    for suffix in ("-cam0", "-cam1"):
        if name.endswith(suffix):
            return name[:-len(suffix)]

    return name


# ============================================================
# DATA NORMALIZATION
# ============================================================

def normalize_coordinates(X_train, X_test):
    """
    Calculate x/y statistics from training data only.
    Apply the same statistics to train and test data.
    Keep confidence values unchanged.
    """

    X_train = X_train.copy()
    X_test = X_test.copy()

    visible_train = X_train[:, :, :, 2] > 0

    means = np.zeros(2, dtype=np.float32)
    stds = np.ones(2, dtype=np.float32)

    for feature in (0, 1):
        values = X_train[:, :, :, feature][visible_train]

        if values.size > 0:
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
# LSTM MODEL
# ============================================================

class LSTMFallDetector(nn.Module):
    """
    LSTM-based fall classifier.

    Each frame contains 17 joints.
    Each joint has x, y and confidence features.

    The 17 joints are flattened into 51 features per frame.
    The LSTM learns temporal movement patterns across 30 frames.
    """

    def __init__(self):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=NUM_JOINTS * INPUT_FEATURES,
            hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS,
            batch_first=True,
            dropout=DROPOUT if NUM_LAYERS > 1 else 0.0,
        )

        self.classifier = nn.Sequential(
            nn.Linear(HIDDEN_SIZE, 32),
            nn.ReLU(),
            nn.Dropout(DROPOUT),
            nn.Linear(32, 2),
        )

    def forward(self, x):
        # Input: batch x time x joints x features
        batch_size = x.size(0)

        # Flatten joints and their features for every frame.
        x = x.reshape(
            batch_size,
            WINDOW_SIZE,
            NUM_JOINTS * INPUT_FEATURES,
        )

        # Output: batch x time x hidden_size
        output, _ = self.lstm(x)

        # Use the final time-step representation.
        final_output = output[:, -1, :]

        return self.classifier(final_output)


# ============================================================
# MAIN TRAINING AND EVALUATION
# ============================================================

def main():
    set_seed(SEED)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Temporal dataset not found: {DATA_FILE}\n"
            "Run the temporal dataset preparation script first."
        )

    if not SPLIT_FILE.exists():
        raise FileNotFoundError(
            f"Common split v2 file not found: {SPLIT_FILE}\n"
            "Create common_split_v2.npz before training this model."
        )

    # --------------------------------------------------------
    # Load temporal skeleton dataset
    # --------------------------------------------------------

    with np.load(DATA_FILE, allow_pickle=False) as data:
        X = data["X"].astype(np.float32)
        y = data["y"].astype(np.int64)
        groups = data["groups"].astype(str)

    # Use the fixed recording-level split shared by CNN and Random Forest.
    # Both camera views of the same recording are normalized to one base ID.
    with np.load(SPLIT_FILE, allow_pickle=False) as split:
        train_sequences = {
            normalize_sequence(s) for s in split["train_sequences"].astype(str)
        }
        test_sequences = {
            normalize_sequence(s) for s in split["test_sequences"].astype(str)
        }

    if train_sequences & test_sequences:
        raise ValueError(
            "Recording leakage detected in common_split_v2.npz: "
            f"{sorted(train_sequences & test_sequences)}"
        )

    expected_shape = (
        WINDOW_SIZE,
        NUM_JOINTS,
        INPUT_FEATURES,
    )

    if X.ndim != 4 or X.shape[1:] != expected_shape:
        raise ValueError(
            f"Unexpected dataset shape: {X.shape}; "
            f"expected (N, {expected_shape})"
        )

    if len(X) != len(y) or len(X) != len(groups):
        raise ValueError(
            "Dataset arrays X, y and groups have different lengths."
        )

    normalized_groups = np.array(
        [normalize_sequence(group) for group in groups]
    )

    # --------------------------------------------------------
    # Sequence-level train/test split
    # --------------------------------------------------------

    train_mask = np.isin(normalized_groups, list(train_sequences))
    test_mask = np.isin(normalized_groups, list(test_sequences))

    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise ValueError(
            "Train/test split is empty. Check the sequence IDs."
        )

    train_groups = set(normalized_groups[train_idx])
    test_groups = set(normalized_groups[test_idx])

    if not train_groups.isdisjoint(test_groups):
        raise ValueError(
            "Sequence leakage detected between training and testing!"
        )

    actual_train_groups = set(normalized_groups[train_idx])
    actual_test_groups = set(normalized_groups[test_idx])

    missing_train_groups = train_sequences - actual_train_groups
    missing_test_groups = test_sequences - actual_test_groups

    if missing_train_groups:
        raise ValueError(
            "Expected training recordings are missing from the dataset: "
            f"{sorted(missing_train_groups)}"
        )

    if missing_test_groups:
        raise ValueError(
            "Expected test recordings are missing from the dataset: "
            f"{sorted(missing_test_groups)}"
        )

    unexpected_train_groups = actual_train_groups - train_sequences
    unexpected_test_groups = actual_test_groups - test_sequences

    if unexpected_train_groups or unexpected_test_groups:
        raise ValueError(
            "Dataset contains recordings outside common_split_v2. "
            f"Unexpected train: {sorted(unexpected_train_groups)}; "
            f"unexpected test: {sorted(unexpected_test_groups)}"
        )

    if set(np.unique(y[train_idx])) != {0, 1}:
        raise ValueError("Training split must contain both normal and fall classes.")

    if set(np.unique(y[test_idx])) != {0, 1}:
        raise ValueError("Testing split must contain both normal and fall classes.")

    X_train = X[train_idx].copy()
    X_test = X[test_idx].copy()

    y_train = y[train_idx]
    y_test = y[test_idx]

    # --------------------------------------------------------
    # Normalize using training data only
    # --------------------------------------------------------

    X_train, X_test, coord_means, coord_stds = (
        normalize_coordinates(X_train, X_test)
    )

    # --------------------------------------------------------
    # Training setup
    # --------------------------------------------------------

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

    model = LSTMFallDetector().to(device)

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

    # --------------------------------------------------------
    # Training information
    # --------------------------------------------------------

    print("=" * 60)
    print("LSTM COMMON-SPLIT TRAINING")
    print("=" * 60)

    print("Device:", device)
    print("Total windows:", len(X))
    print("Training windows:", len(train_idx))
    print("Testing windows:", len(test_idx))
    print("Training recordings:", len(train_groups))
    print("Testing recordings:", len(test_groups))
    print("Test recording IDs:", sorted(test_groups))

    print(
        "Train class counts [normal, fall]:",
        class_counts,
    )

    print(
        "Test class counts [normal, fall]:",
        np.bincount(y_test, minlength=2),
    )

    print("Coordinate means [x, y]:", coord_means)
    print("Coordinate stds [x, y]:", coord_stds)

    # --------------------------------------------------------
    # Train LSTM
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
    # Evaluate on the fixed test set
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
        y_test,
        predictions,
        zero_division=0,
    )

    recall = recall_score(
        y_test,
        predictions,
        zero_division=0,
    )

    f1 = f1_score(
        y_test,
        predictions,
        zero_division=0,
    )

    cm = confusion_matrix(
        y_test,
        predictions,
        labels=[0, 1],
    )

    print("\n" + "=" * 60)
    print("LSTM TEST RESULTS")
    print("=" * 60)

    print(f"Accuracy:          {accuracy:.4f}")
    print(f"Fall precision:    {precision:.4f}")
    print(f"Fall recall:       {recall:.4f}")
    print(f"Fall F1-score:     {f1:.4f}")
    print(f"Training time:     {training_seconds:.2f} seconds")
    print(f"Test inference:    {inference_seconds:.4f} seconds")

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
    # Save model and results
    # --------------------------------------------------------

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "lstm_fall_detection_common_split.pt"

    result_path = RESULT_DIR / "lstm_common_split_results.npz"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "window_size": WINDOW_SIZE,
            "num_joints": NUM_JOINTS,
            "input_features": INPUT_FEATURES,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "class_names": ["normal", "fall"],
            "coordinate_means": coord_means,
            "coordinate_stds": coord_stds,
            "test_sequences": sorted(test_groups),
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
    print("\nLSTM training and evaluation complete.")


if __name__ == "__main__":
    main()
