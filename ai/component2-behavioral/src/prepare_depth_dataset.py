
import csv
from pathlib import Path

import numpy as np

BASE = Path("ai/component2-behavioral/data/external")
OUTPUT = Path("ai/component2-behavioral/data/processed/depth")

FILES = [
    "urfall-cam0-falls.csv",
    "urfall-cam0-adls.csv",
]

OUTPUT.mkdir(parents=True, exist_ok=True)

X = []
y = []
sequences = []

for filename in FILES:
    path = BASE / filename

    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) != 11:
                continue

            sequence, frame, label = row[:3]
            label = int(label)

            # Exclude temporary falling-transition poses.
            if label == 0:
                continue

            features = [float(value) for value in row[3:11]]

            # Class 0: not lying on the ground.
            # Class 1: lying on the ground.
            X.append(features)
            y.append(1 if label == 1 else 0)
            sequences.append(sequence)

X = np.asarray(X, dtype=np.float32)
y = np.asarray(y, dtype=np.int64)
sequences = np.asarray(sequences)

np.savez_compressed(
    OUTPUT / "depth_dataset.npz",
    X=X,
    y=y,
    sequences=sequences,
)

print("Dataset saved:", OUTPUT / "depth_dataset.npz")
print("Feature matrix shape:", X.shape)
print("Labels shape:", y.shape)
print("Not lying (class 0):", int(np.sum(y == 0)))
print("Lying (class 1):", int(np.sum(y == 1)))
print("Unique sequences:", len(np.unique(sequences)))
print("Feature columns:", 8)
