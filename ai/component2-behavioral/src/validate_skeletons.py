
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
SKELETON_DIR = BASE_DIR / "data" / "processed" / "skeletons"


def main():
    files = sorted(SKELETON_DIR.glob("*.npz"))

    if not files:
        print("No skeleton files found.")
        return

    for file_path in files:
        with np.load(file_path, allow_pickle=False) as data:
            keypoints = data["keypoints"]
            label = str(data["label"].item())
            camera = int(data["camera"].item())

        # A frame has detected keypoints if at least one joint
        # has a positive confidence score.
        detected_frames = np.any(keypoints[:, :, 2] > 0, axis=1)
        missing_frames = len(detected_frames) - int(detected_frames.sum())

        print(f"\nSequence: {file_path.stem}")
        print(f"  Label: {label}")
        print(f"  Camera: {camera}")
        print(f"  Shape: {keypoints.shape}")
        print(f"  Frames with keypoints: {detected_frames.sum()}")
        print(f"  Frames without keypoints: {missing_frames}")
        print(
            "  Confidence range:",
            float(keypoints[:, :, 2].min()),
            "to",
            float(keypoints[:, :, 2].max()),
        )

        assert keypoints.ndim == 3
        assert keypoints.shape[1:] == (17, 3)

    print("\nSkeleton validation completed.")


if __name__ == "__main__":
    main()
