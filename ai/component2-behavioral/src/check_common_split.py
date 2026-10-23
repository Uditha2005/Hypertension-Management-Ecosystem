
from pathlib import Path

import numpy as np

temporal_path = Path(
    "ai/component2-behavioral/data/processed/temporal/temporal_dataset.npz"
)
depth_path = Path(
    "ai/component2-behavioral/data/processed/results/depth_baseline_results.npz"
)

with np.load(temporal_path, allow_pickle=False) as data:
    groups = data["groups"]
    y = data["y"]

with np.load(depth_path, allow_pickle=False) as data:
    depth_test_sequences = {
        str(s) for s in data["test_sequences"]
    }

# Remove camera suffix so "fall-06-cam0" matches "fall-06".
normalize = lambda s: str(s).removesuffix("-cam0").removesuffix("-cam1")

test_mask = np.array([
    normalize(g) in depth_test_sequences
    for g in groups
])

train_mask = ~test_mask

print("Depth test sequences:", len(depth_test_sequences))
print("Skeleton test windows:", int(test_mask.sum()))
print("Skeleton train windows:", int(train_mask.sum()))

print(
    "Skeleton test class counts [normal, fall]:",
    np.bincount(y[test_mask], minlength=2),
)
print(
    "Skeleton train class counts [normal, fall]:",
    np.bincount(y[train_mask], minlength=2),
)

print("\nTest sequences represented in skeleton data:")
for sequence in sorted(set(normalize(g) for g in groups[test_mask])):
    mask = np.array([normalize(g) == sequence for g in groups])
    print(
        sequence,
        "| windows:", int(mask.sum()),
        "| labels [normal, fall]:",
        np.bincount(y[mask], minlength=2).tolist(),
    )

print("\nAll depth test sequences represented:",
      all(
          s in set(normalize(g) for g in groups)
          for s in depth_test_sequences
      ))
