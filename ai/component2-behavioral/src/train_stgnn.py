
from pathlib import Path
import random

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import GroupShuffleSplit
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
MODEL_DIR = BASE_DIR / "models"
RESULT_DIR = BASE_DIR / "data" / "processed" / "results"

WINDOW_SIZE = 30
NUM_JOINTS = 17
INPUT_FEATURES = 3
BATCH_SIZE = 32
EPOCHS = 40
LEARNING_RATE = 0.001
SEED = 42

# COCO-17 skeleton edges (zero-based indices).
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
            "adjacency", torch.tensor(adjacency, dtype=torch.float32)
        )

        self.spatial1 = nn.Linear(INPUT_FEATURES, 32)
        self.spatial2 = nn.Linear(32, 64)

        # Temporal convolution operates across the 30-frame dimension.
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
        x = x.mean(dim=2)           # batch x time x 64
        x = x.transpose(1, 2)       # batch x 64 x time
        x = self.temporal(x)
        x = x.mean(dim=2)            # temporal pooling
        return self.classifier(x)


def main():
    set_seed(SEED)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Temporal dataset not found: {DATA_FILE}\n"
            "Run prepare_temporal_dataset.py first."
        )

    with np.load(DATA_FILE, allow_pickle=False) as data:
        X = data["X"].astype(np.float32)
        y = data["y"].astype(np.int64)
        groups = data["groups"].astype(str)

    if X.ndim != 4 or X.shape[1:] != (WINDOW_SIZE, NUM_JOINTS, INPUT_FEATURES):
        raise ValueError(f"Unexpected dataset shape: {X.shape}")

    # Split by sequence, not by overlapping windows.
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=0.25, random_state=SEED
    )
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))

    train_groups = set(groups[train_idx])
    test_groups = set(groups[test_idx])
    assert train_groups.isdisjoint(test_groups), "Sequence leakage detected!"

    X_train, X_test = X[train_idx].copy(), X[test_idx].copy()
    y_train, y_test = y[train_idx], y[test_idx]

    # Balance the loss for the smaller fall class.
    counts = np.bincount(y_train, minlength=2)
    class_weights = len(y_train) / (
        2.0 * np.maximum(counts, 1)
    )

    # Normalize x/y coordinates only using visible joints.
    # Confidence values remain in their original [0, 1] range.
    for array in (X_train, X_test):
        visible = array[:, :, :, 2] > 0
        for feature in (0, 1):
            values = array[:, :, :, feature]
            if visible.any():
                values[visible] = (
                    values[visible] - values[visible].mean()
                ) / (values[visible].std() + 1e-6)
            values[~visible] = 0.0

    train_dataset = TensorDataset(
        torch.from_numpy(X_train), torch.from_numpy(y_train)
    )
    train_loader = DataLoader(
        train_dataset, batch_size=BATCH_SIZE, shuffle=True
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = STGNN(build_adjacency()).to(device)
    weights = torch.tensor(class_weights, dtype=torch.float32, device=device)

    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4
    )

    print("===== ST-GNN TRAINING =====")
    print("Device:", device)
    print("Total windows:", len(X))
    print("Training windows:", len(train_idx))
    print("Testing windows:", len(test_idx))
    print("Training sequences:", len(train_groups))
    print("Testing sequences:", len(test_groups))
    print("Train class counts [normal, fall]:", counts)
    print("Test class counts [normal, fall]:",
          np.bincount(y_test, minlength=2))

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
            print(f"Epoch {epoch + 1:02d}/{EPOCHS} | Loss: {avg_loss:.4f}")

    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(X_test).to(device))
        predictions = logits.argmax(dim=1).cpu().numpy()

    print("\n===== TEST RESULTS =====")
    print(f"Accuracy:  {accuracy_score(y_test, predictions):.4f}")
    print(f"Precision: {precision_score(y_test, predictions, zero_division=0):.4f}")
    print(f"Recall:    {recall_score(y_test, predictions, zero_division=0):.4f}")
    print(f"F1-score:  {f1_score(y_test, predictions, zero_division=0):.4f}")
    print("\nClassification report:")
    print(classification_report(
        y_test, predictions,
        labels=[0, 1],
        target_names=["Normal", "Fall"],
        zero_division=0,
    ))

    cm = confusion_matrix(y_test, predictions, labels=[0, 1])
    print("Confusion matrix [normal, fall]:")
    print(cm)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "adjacency": build_adjacency(),
            "window_size": WINDOW_SIZE,
            "class_names": ["normal", "fall"],
        },
        MODEL_DIR / "stgnn_fall_detection.pt",
    )

    np.savez_compressed(
        RESULT_DIR / "stgnn_test_results.npz",
        y_true=y_test,
        y_pred=predictions,
        confusion_matrix=cm,
        test_groups=groups[test_idx],
    )

    print("\nSaved model:", MODEL_DIR / "stgnn_fall_detection.pt")
    print("Saved evaluation:", RESULT_DIR / "stgnn_test_results.npz")


if __name__ == "__main__":
    main()
