
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "skeletons"

MODEL_NAME = "yolo11n-pose.pt"

SEQUENCES = [
    {
        "name": "fall-01-cam0",
        "folder": DATA_DIR / "fall" / "fall-01-cam0-rgb",
        "label": "fall",
        "camera": 0,
    },
    {
        "name": "fall-01-cam1",
        "folder": DATA_DIR / "fall" / "fall-01-cam1-rgb",
        "label": "fall",
        "camera": 1,
    },
    {
        "name": "adl-01-cam0",
        "folder": DATA_DIR / "normal" / "adl-01-cam0-rgb",
        "label": "normal",
        "camera": 0,
    },
]


def numeric_sort(path):
    """Sort frame-1, frame-2, frame-10 in numeric order."""
    return int(path.stem.rsplit("-", 1)[-1])


def extract_sequence(model, sequence):
    folder = sequence["folder"]

    if not folder.exists():
        print(f"[SKIP] Folder not found: {folder}")
        return

    image_paths = sorted(folder.glob("*.png"), key=numeric_sort)

    if not image_paths:
        print(f"[SKIP] No PNG frames in {folder}")
        return

    # Each frame: 17 COCO body keypoints, each with x, y, confidence.
    all_keypoints = []
    valid_frames = 0

    print(f"\nProcessing {sequence['name']} ({len(image_paths)} frames)")

    for index, image_path in enumerate(image_paths, start=1):
        frame = cv2.imread(str(image_path))

        if frame is None:
            print(f"[WARNING] Cannot read {image_path.name}")
            all_keypoints.append(np.zeros((17, 3), dtype=np.float32))
            continue

        result = model.predict(
            frame,
            conf=0.25,
            verbose=False
        )[0]

        frame_keypoints = np.zeros((17, 3), dtype=np.float32)

        if result.keypoints is not None and len(result.keypoints.data) > 0:
            people = result.keypoints.data.cpu().numpy()

            # Select the person with the highest detection confidence.
            if result.boxes is not None:
                scores = result.boxes.conf.cpu().numpy()
                person_index = int(np.argmax(scores))
            else:
                person_index = 0

            if person_index < len(people):
                frame_keypoints = people[person_index].astype(np.float32)
                valid_frames += 1

        all_keypoints.append(frame_keypoints)

        if index % 25 == 0 or index == len(image_paths):
            print(f"  Processed {index}/{len(image_paths)} frames")

    keypoint_array = np.stack(all_keypoints, axis=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{sequence['name']}.npz"

    np.savez_compressed(
        output_file,
        keypoints=keypoint_array,
        label=np.array(sequence["label"]),
        camera=np.array(sequence["camera"]),
        frame_names=np.array([p.name for p in image_paths]),
    )

    print(f"  Detected person: {valid_frames}/{len(image_paths)} frames")
    print(f"  Saved: {output_file}")
    print(f"  Keypoint array shape: {keypoint_array.shape}")


def main():
    model = YOLO(MODEL_NAME)

    for sequence in SEQUENCES:
        extract_sequence(model, sequence)

    print("\nSkeleton extraction completed.")


if __name__ == "__main__":
    main()
