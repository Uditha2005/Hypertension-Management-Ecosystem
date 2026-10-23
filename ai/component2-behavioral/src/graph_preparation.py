
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "data" / "processed" / "skeletons"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "graphs"

# COCO-17 skeleton connections, using zero-based joint indices.
SKELETON_EDGES = [
    (0, 1), (0, 2),
    (1, 3), (2, 4),
    (5, 6),
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for file_path in sorted(INPUT_DIR.glob("*-cam1.npz")):
        with np.load(file_path, allow_pickle=False) as data:
            keypoints = data["keypoints"].astype(np.float32)
            label = data["label"]
            camera = data["camera"]
            frame_names = data["frame_names"]

        # Normalize x and y coordinates using image dimensions.
        # The source frames are 640x480.
        keypoints[:, :, 0] /= 640.0
        keypoints[:, :, 1] /= 480.0

        # Replace coordinates of joints with zero confidence.
        # Keep confidence as the third feature.
        invisible = keypoints[:, :, 2] <= 0
        keypoints[:, :, :2][invisible] = 0.0

        # Graph edges are shared across all frames.
        edges = np.asarray(SKELETON_EDGES, dtype=np.int64)

        output_path = OUTPUT_DIR / f"{file_path.stem}_graph.npz"

        np.savez_compressed(
            output_path,
            node_features=keypoints,
            edge_index=edges,
            label=label,
            camera=camera,
            frame_names=frame_names,
        )

        print(f"Saved: {output_path}")
        print(f"  Node features: {keypoints.shape}")
        print(f"  Skeleton edges: {edges.shape[0]}")

    print("\nGraph preparation completed.")


if __name__ == "__main__":
    main()
