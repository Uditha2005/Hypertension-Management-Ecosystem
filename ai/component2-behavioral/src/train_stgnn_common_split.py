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

BATCH_SIZE = 32
EPOCHS = 40
LEARNING_RATE = 0.001
SEED = 42

SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8),
    (8, 10), (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # Deterministic settings improve repeatability where supported.
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


# ============================================================
# RECORDING ID NORMALIZATION
# ============================================================

def normalize_sequence(name):
    """Map fall-06-cam0 and fall-06-cam1 to the same base ID."""
    name = str(name)

    for suffix in ("-cam0", "-cam1"):
        if name.endswith(suffix):
            return name[:-len(suffix)]

    return name


# ============================================================
# SKELETON ADJACENCY MATRIX
# ============================================================

def build_adjacency():
    adjacency = np.eye(NUM_JOINTS, dtype=np.float32)

    for a, b in SKELETON_EDGES:
        adjacency[a, b] = 1.0
        adjacency[b, a] = 1.0

    degree = adjacency.sum(axis=1)
    inv_sqrt_degree = np.diag(1.0 / np.sqrt(degree))

    return inv_sqrt_degree @ adjacency @ inv_sqrt_degree


# ============================================================
# TRAINING-ONLY COORDINATE NORMALIZATION
# ============================================================

def normalize_coordinates(X_train, X_test):
    """
    Estimate x/y statistics from visible joints in the training set only.
    Apply the same statistics to train and test. Confidence is unchanged.
    """
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
# SPATIO-TEMPORAL GRAPH NEURAL NETWORK
# ============================================================

class STGNN(nn.Module):
    def __init__(self, adjacency):
        super().__init__()

        self.register_buffer(
            "adjacency",
            torch.tensor(adjacency, dtype=torch.float32),
        )

        self.spatial1 = nn.Linear(INPUT_FEATURES, 32)
        self.spatial2 = nn.Linear(32, 64)

        self.temporal = nn.Sequential(
            nn.Conv1d(64, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Conv1d(64, 64, kernel_size=3, padding=1),
            nn.ReLU(),
        )

        self.classifier = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.30),
            nn.Linear(32, 2),
        )

    def forward(self, x):
        # x shape: batch x time x joints x features
        # Aggregate neighboring joint features using the normalized graph.
        x = torch.matmul(self.adjacency, x)
        x = torch.relu(self.spatial1(x))

        x = torch.matmul(self.adjacency, x)
        x = torch.relu(self.spatial2(x))

        # Average joint representations at each time step.
        x = x.mean(dim=2)       # batch x time x 64
        x = x.transpose(1, 2)   # batch x 64 x time

        x = self.temporal(x)
        x = x.mean(dim=2)       # global temporal pooling

        return self.classifier(x)


# ============================================================
# MAIN TRAINING AND EVALUATION
# ============================================================

def main():
    set_seed(SEED)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Temporal dataset not found: {DATA_FILE}\n"
            "Run src/prepare_temporal_dataset.py first."
        )

    if not SPLIT_FILE.exists():
        raise FileNotFoundError(
            f"Shared split file not found: {SPLIT_FILE}\n"
            "Create common_split_v2.npz before training."
        )

    # --------------------------------------------------------
    # Load the full temporal dataset
    # --------------------------------------------------------

    with np.load(DATA_FILE, allow_pickle=False) as data:
        X = data["X"].astype(np.float32)
        y = data["y"].astype(np.int64)
        groups = data["groups"].astype(str)

    expected_shape = (WINDOW_SIZE, NUM_JOINTS, INPUT_FEATURES)

    if X.ndim != 4 or X.shape[1:] != expected_shape:
        raise ValueError(
            f"Unexpected temporal dataset shape: {X.shape}; "
            f"expected (N, {expected_shape})"
        )

    if not (len(X) == len(y) == len(groups)):
        raise ValueError(
            "Dataset arrays X, y and groups have different lengths."
        )

    if not set(np.unique(y)).issubset({0, 1}):
        raise ValueError("Labels must be 0=normal and 1=fall.")

    normalized_groups = np.array(
        [normalize_sequence(group) for group in groups],
        dtype=str,
    )

    # --------------------------------------------------------
    # Load the SAME recording-level split as CNN and RF
    # --------------------------------------------------------

    with np.load(SPLIT_FILE, allow_pickle=False) as split:
        if "train_sequences" not in split or "test_sequences" not in split:
            raise KeyError(
                "common_split_v2.npz must contain train_sequences "
                "and test_sequences."
            )

        train_sequences = {
            normalize_sequence(s)
            for s in split["train_sequences"].astype(str)
        }
        test_sequences = {
            normalize_sequence(s)
            for s in split["test_sequences"].astype(str)
        }

    overlap = train_sequences & test_sequences
    if overlap:
        raise ValueError(
            "Recording leakage found in common_split_v2.npz: "
            f"{sorted(overlap)}"
        )

    train_mask = np.isin(normalized_groups, list(train_sequences))
    test_mask = np.isin(normalized_groups, list(test_sequences))

    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise ValueError(
            "Train/test split is empty. Check common_split_v2.npz."
        )

    actual_train_groups = set(normalized_groups[train_idx])
    actual_test_groups = set(normalized_groups[test_idx])

    if not actual_train_groups.isdisjoint(actual_test_groups):
        raise ValueError("Recording leakage detected between train and test.")

    missing_train = train_sequences - actual_train_groups
    missing_test = test_sequences - actual_test_groups

    if missing_train:
        raise ValueError(
            "Training recordings missing from dataset: "
            f"{sorted(missing_train)}"
        )

    if missing_test:
        raise ValueError(
            "Test recordings missing from dataset: "
            f"{sorted(missing_test)}"
        )

    unexpected_train = actual_train_groups - train_sequences
    unexpected_test = actual_test_groups - test_sequences

    if unexpected_train or unexpected_test:
        raise ValueError(
            "Dataset includes recordings outside the shared split. "
            f"Unexpected train={sorted(unexpected_train)}, "
            f"unexpected test={sorted(unexpected_test)}"
        )

    X_train = X[train_idx].copy()
    X_test = X[test_idx].copy()
    y_train = y[train_idx]
    y_test = y[test_idx]

    if set(np.unique(y_train)) != {0, 1}:
        raise ValueError("Training split must contain normal and fall samples.")

    if set(np.unique(y_test)) != {0, 1}:
        raise ValueError("Test split must contain normal and fall samples.")

    # --------------------------------------------------------
    # Normalize using training data only
    # --------------------------------------------------------

    X_train, X_test, coord_means, coord_stds = normalize_coordinates(
        X_train,
        X_test,
    )

    # --------------------------------------------------------
    # Data loader, model and optimizer
    # --------------------------------------------------------

    train_counts = np.bincount(y_train, minlength=2)
    class_weights = len(y_train) / (
        2.0 * np.maximum(train_counts, 1)
    )

    train_dataset = TensorDataset(
        torch.from_numpy(X_train),
        torch.from_numpy(y_train),
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    adjacency = build_adjacency()
    model = STGNN(adjacency).to(device)

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
    print("ST-GNN COMMON-SPLIT V2 TRAINING")
    print("=" * 60)
    print("Device:", device)
    print("Total windows:", len(X))
    print("Training windows:", len(train_idx))
    print("Testing windows:", len(test_idx))
    print("Training recordings:", len(actual_train_groups))
    print("Testing recordings:", len(actual_test_groups))
    print("Test recording IDs:", sorted(actual_test_groups))
    print("Train class counts [normal, fall]:", train_counts)
    print("Test class counts [normal, fall]:", np.bincount(y_test, minlength=2))
    print("Coordinate means [x, y]:", coord_means)
    print("Coordinate stds [x, y]:", coord_stds)
    print("Recording leakage: None")

    # --------------------------------------------------------
    # Train
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

    if device.type == "cuda":
        torch.cuda.synchronize()
    training_seconds = time.perf_counter() - training_start

    # --------------------------------------------------------
    # Evaluate once on the fixed test set
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
    precision = precision_score(y_test, predictions, zero_division=0)
    recall = recall_score(y_test, predictions, zero_division=0)
    f1 = f1_score(y_test, predictions, zero_division=0)
    cm = confusion_matrix(y_test, predictions, labels=[0, 1])

    print("\n" + "=" * 60)
    print("ST-GNN TEST RESULTS")
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
    # Save model and evaluation results
    # --------------------------------------------------------

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "stgnn_fall_detection_common_split.pt"
    result_path = RESULT_DIR / "stgnn_common_split_results.npz"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "adjacency": adjacency,
            "window_size": WINDOW_SIZE,
            "num_joints": NUM_JOINTS,
            "input_features": INPUT_FEATURES,
            "class_names": ["normal", "fall"],
            "coordinate_means": coord_means,
            "coordinate_stds": coord_stds,
            "train_sequences": sorted(actual_train_groups),
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
        normalized_train_groups=normalized_groups[train_idx],
        train_sequences=np.array(sorted(actual_train_groups), dtype=str),
        test_sequences=np.array(sorted(actual_test_groups), dtype=str),
        accuracy=np.array(accuracy),
        precision=np.array(precision),
        recall=np.array(recall),
        f1=np.array(f1),
        training_seconds=np.array(training_seconds),
        inference_seconds=np.array(inference_seconds),
        feature_count=np.array(NUM_JOINTS * INPUT_FEATURES),
        seed=np.array(SEED),
    )

    print("\nSaved model:", model_path)
    print("Saved evaluation:", result_path)
    print("\nST-GNN training and evaluation complete.")


if __name__ == "__main__":
    main()
