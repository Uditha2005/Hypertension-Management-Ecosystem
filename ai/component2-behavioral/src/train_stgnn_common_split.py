
from pathlib import Path
import random

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

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR / "data" / "processed" / "temporal" / "temporal_dataset.npz"
)
DEPTH_RESULTS_FILE = (
    BASE_DIR / "data" / "processed" / "results" / "depth_baseline_results.npz"
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


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def normalize_sequence(name):
    """Convert names such as fall-06-cam0 to fall-06."""
    name = str(name)

    for suffix in ("-cam0", "-cam1"):
        if name.endswith(suffix):
            return name[:-len(suffix)]

    return name


def build_adjacency():
    adjacency = np.eye(NUM_JOINTS, dtype=np.float32)

    for a, b in SKELETON_EDGES:
        adjacency[a, b] = 1.0
        adjacency[b, a] = 1.0

    degree = adjacency.sum(axis=1)
    inv_sqrt_degree = np.diag(1.0 / np.sqrt(degree))

    return inv_sqrt_degree @ adjacency @ inv_sqrt_degree


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
            nn.Dropout(0.3),
            nn.Linear(32, 2),
        )

    def forward(self, x):
        # x: batch x time x joints x features
        x = torch.matmul(self.adjacency, x)
        x = torch.relu(self.spatial1(x))

        x = torch.matmul(self.adjacency, x)
        x = torch.relu(self.spatial2(x))

        # Average joint features at each time step.
        x = x.mean(dim=2)
        x = x.transpose(1, 2)

        x = self.temporal(x)
        x = x.mean(dim=2)

        return self.classifier(x)


def normalize_coordinates(X_train, X_test):
    """
    Calculate coordinate statistics from training data only.
    Apply the same statistics to training and test data.
    Confidence values remain unchanged.
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


def main():
    set_seed(SEED)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Temporal dataset not found: {DATA_FILE}"
        )

    if not DEPTH_RESULTS_FILE.exists():
        raise FileNotFoundError(
            f"Depth test split not found: {DEPTH_RESULTS_FILE}\n"
            "Run train_depth_baseline.py first."
        )

    with np.load(DATA_FILE, allow_pickle=False) as data:
        X = data["X"].astype(np.float32)
        y = data["y"].astype(np.int64)
        groups = data["groups"].astype(str)

    with np.load(DEPTH_RESULTS_FILE, allow_pickle=False) as data:
        depth_test_sequences = {
            normalize_sequence(s)
            for s in data["test_sequences"]
        }

    if X.ndim != 4 or X.shape[1:] != (
        WINDOW_SIZE,
        NUM_JOINTS,
        INPUT_FEATURES,
    ):
        raise ValueError(f"Unexpected dataset shape: {X.shape}")

    # Use the same held-out sequence IDs as the depth baseline.
    normalized_groups = np.array([
        normalize_sequence(group) for group in groups
    ])

    test_mask = np.isin(
        normalized_groups,
        list(depth_test_sequences),
    )

    train_mask = ~test_mask

    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)

    if len(test_idx) == 0 or len(train_idx) == 0:
        raise ValueError("Train/test split is empty. Check sequence IDs.")

    train_groups = set(normalized_groups[train_idx])
    test_groups = set(normalized_groups[test_idx])

    assert train_groups.isdisjoint(test_groups), (
        "Sequence leakage detected!"
    )

    # Check that every intended held-out sequence exists.
    represented_test_groups = set(normalized_groups[test_idx])
    missing_test_groups = depth_test_sequences - represented_test_groups

    if missing_test_groups:
        raise ValueError(
            f"Depth test sequences missing from skeleton data: "
            f"{sorted(missing_test_groups)}"
        )

    X_train = X[train_idx].copy()
    X_test = X[test_idx].copy()

    y_train = y[train_idx]
    y_test = y[test_idx]

    # Normalize using training statistics only.
    X_train, X_test, coord_means, coord_stds = normalize_coordinates(
        X_train,
        X_test,
    )

    counts = np.bincount(y_train, minlength=2)
    class_weights = len(y_train) / (
        2.0 * np.maximum(counts, 1)
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

    print("===== ST-GNN COMMON-SPLIT TRAINING =====")
    print("Device:", device)
    print("Total windows:", len(X))
    print("Training windows:", len(train_idx))
    print("Testing windows:", len(test_idx))
    print("Training sequences:", len(train_groups))
    print("Testing sequences:", len(test_groups))
    print("Test sequence IDs:", sorted(test_groups))
    print("Train class counts [normal, fall]:", counts)
    print(
        "Test class counts [normal, fall]:",
        np.bincount(y_test, minlength=2),
    )
    print("Coordinate means [x, y]:", coord_means)
    print("Coordinate stds [x, y]:", coord_stds)

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
            avg_loss = total_loss / len(train_dataset)

            print(
                f"Epoch {epoch + 1:02d}/{EPOCHS} "
                f"| Loss: {avg_loss:.4f}"
            )

    model.eval()

    with torch.no_grad():
        logits = model(torch.from_numpy(X_test).to(device))
        predictions = logits.argmax(dim=1).cpu().numpy()

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

    print("\n===== TEST RESULTS =====")
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-score:  {f1:.4f}")

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

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "stgnn_fall_detection_common_split.pt"
    result_path = RESULT_DIR / "stgnn_common_split_results.npz"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "adjacency": adjacency,
            "window_size": WINDOW_SIZE,
            "class_names": ["normal", "fall"],
            "coordinate_means": coord_means,
            "coordinate_stds": coord_stds,
            "test_sequences": sorted(test_groups),
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
    )

    print("\nSaved model:", model_path)
    print("Saved evaluation:", result_path)


if __name__ == "__main__":
    main()
