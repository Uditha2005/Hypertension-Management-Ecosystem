
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "data" / "processed" / "graphs"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "temporal"
OUTPUT_FILE = OUTPUT_DIR / "temporal_dataset.npz"

WINDOW_SIZE = 30
STRIDE = 15


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    samples = []
    labels = []
    groups = []

    graph_files = sorted(INPUT_DIR.glob("*_graph.npz"))

    for file_path in graph_files:
        with np.load(file_path, allow_pickle=False) as data:
            sequence = data["node_features"].astype(np.float32)
            label_name = str(data["label"].item())

        # 0 = normal, 1 = fall
        label = 1 if label_name == "fall" else 0

        if len(sequence) < WINDOW_SIZE:
            print(f"[SKIP] Too short: {file_path.name}")
            continue

        for start in range(0, len(sequence) - WINDOW_SIZE + 1, STRIDE):
            window = sequence[start:start + WINDOW_SIZE]

            # Ignore windows with very little detected pose information.
            visible = window[:, :, 2] > 0
            if visible.sum() < WINDOW_SIZE * 3:
                continue

            samples.append(window)
            labels.append(label)

            # Keep the source sequence name for group-based splitting.
            groups.append(file_path.stem.replace("_graph", ""))

        print(f"Processed: {file_path.name}")

    if not samples:
        raise RuntimeError("No valid temporal windows were created.")

    X = np.stack(samples).astype(np.float32)
    y = np.asarray(labels, dtype=np.int64)
    group_ids = np.asarray(groups)

    np.savez_compressed(
        OUTPUT_FILE,
        X=X,
        y=y,
        groups=group_ids,
    )

    print("\n===== TEMPORAL DATASET SUMMARY =====")
    print("Total windows:", len(X))
    print("Window shape:", X.shape)
    print("Normal windows:", int((y == 0).sum()))
    print("Fall windows:", int((y == 1).sum()))
    print("Unique sequences:", len(np.unique(group_ids)))
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
