
from pathlib import Path
import re

import cv2
import numpy as np
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "processed" / "skeletons"

MODEL_NAME = "yolo11n-pose.pt"


def numeric_sort(path):
    """Sort frame-1, frame-2, frame-10 in numeric order."""
    match = re.search(r"-(\d+)$", path.stem)
    return int(match.group(1)) if match else path.stem


def get_sequences():
    """Automatically discover all fall and normal ADL sequences."""
    sequences = []

    fall_dir = DATA_DIR / "fall"
    if fall_dir.exists():
        for folder in sorted(fall_dir.glob("fall-*-cam*-rgb")):
            match = re.search(r"-cam(\d+)-rgb$", folder.name)
            camera = int(match.group(1)) if match else -1

            sequences.append({
                "name": folder.name.removesuffix("-rgb"),
                "folder": folder,
                "label": "fall",
                "camera": camera,
            })

    normal_dir = DATA_DIR / "normal"
    if normal_dir.exists():
        for folder in sorted(normal_dir.glob("adl-*-cam*-rgb")):
            match = re.search(r"-cam(\d+)-rgb$", folder.name)
            camera = int(match.group(1)) if match else -1

            sequences.append({
                "name": folder.name.removesuffix("-rgb"),
                "folder": folder,
                "label": "normal",
                "camera": camera,
            })

    return sequences


def extract_sequence(model, sequence):
    folder = sequence["folder"]

    image_paths = sorted(folder.glob("*.png"), key=numeric_sort)

    if not image_paths:
        print(f"[SKIP] No PNG frames found: {folder}")
        return

    output_file = OUTPUT_DIR / f"{sequence['name']}.npz"

    # Avoid repeating expensive inference if the sequence is already processed.
    if output_file.exists():
        print(f"[SKIP] Already processed: {output_file.name}")
        return

    all_keypoints = []
    valid_frames = 0

    print(
        f"\nProcessing {sequence['name']} "
        f"| Label: {sequence['label']} "
        f"| Frames: {len(image_paths)}"
    )

    for index, image_path in enumerate(image_paths, start=1):
        frame = cv2.imread(str(image_path))

        frame_keypoints = np.zeros((17, 3), dtype=np.float32)

        if frame is None:
            print(f"[WARNING] Cannot read {image_path.name}")
        else:
            result = model.predict(
                frame,
                conf=0.25,
                verbose=False
            )[0]

            if (
                result.keypoints is not None
                and result.keypoints.data is not None
                and len(result.keypoints.data) > 0
            ):
                people = result.keypoints.data.cpu().numpy()

                if result.boxes is not None and len(result.boxes) > 0:
                    scores = result.boxes.conf.cpu().numpy()
                    person_index = int(np.argmax(scores))
                else:
                    person_index = 0

                if person_index < len(people):
                    frame_keypoints = people[person_index].astype(
                        np.float32
                    )
                    valid_frames += 1

        all_keypoints.append(frame_keypoints)

        if index % 25 == 0 or index == len(image_paths):
            print(f"  Processed {index}/{len(image_paths)} frames")

    keypoint_array = np.stack(all_keypoints, axis=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        output_file,
        keypoints=keypoint_array,
        label=np.array(sequence["label"]),
        camera=np.array(sequence["camera"]),
        frame_names=np.array([p.name for p in image_paths]),
    )

    print(f"  Person detected: {valid_frames}/{len(image_paths)} frames")
    print(f"  Saved: {output_file}")
    print(f"  Keypoint shape: {keypoint_array.shape}")


def main():
    sequences = get_sequences()

    if not sequences:
        print("[ERROR] No fall or normal sequences found.")
        return

    fall_count = sum(s["label"] == "fall" for s in sequences)
    normal_count = sum(s["label"] == "normal" for s in sequences)

    print("========== SKELETON EXTRACTION ==========")
    print(f"Fall sequences: {fall_count}")
    print(f"Normal sequences: {normal_count}")
    print(f"Total sequences: {len(sequences)}")

    model = YOLO(MODEL_NAME)

    for sequence in sequences:
        extract_sequence(model, sequence)

    print("\nSkeleton extraction completed.")


if __name__ == "__main__":
    main()
