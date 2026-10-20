
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"
TEMPORAL_FILE = DATA_DIR / "temporal" / "temporal_dataset.npz"
RESULT_FILE = DATA_DIR / "results" / "stgnn_test_results.npz"

with np.load(TEMPORAL_FILE, allow_pickle=False) as data:
    all_groups = data["groups"].astype(str)
    all_labels = data["y"]

with np.load(RESULT_FILE, allow_pickle=False) as data:
    y_true = data["y_true"]
    y_pred = data["y_pred"]
    test_groups = data["test_groups"].astype(str)
    cm = data["confusion_matrix"]

print("===== TEST SEQUENCE DIAGNOSTICS =====")
print("Confusion matrix:")
print(cm)

for group in sorted(np.unique(test_groups)):
    mask = test_groups == group
    actual = y_true[mask]
    predicted = y_pred[mask]

    fall_recall = (
        ((actual == 1) & (predicted == 1)).sum()
        / max((actual == 1).sum(), 1)
    )

    print(
        f"{group:22s} | windows={mask.sum():3d} "
        f"| actual_fall={(actual == 1).sum():3d} "
        f"| predicted_fall={(predicted == 1).sum():3d} "
        f"| fall_recall={fall_recall:.2f}"
    )

print("\nSaved test windows:", len(y_true))
print("Test sequences:", len(np.unique(test_groups)))
print("Original windows:", len(all_labels))
print("Original sequences:", len(np.unique(all_groups)))
