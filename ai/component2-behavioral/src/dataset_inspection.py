
from pathlib import Path
import cv2

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEQUENCES = {
    "Fall - Camera 0": DATA_DIR / "fall" / "fall-01-cam0-rgb",
    "Fall - Camera 1": DATA_DIR / "fall" / "fall-01-cam1-rgb",
    "Normal ADL - Camera 0": DATA_DIR / "normal" / "adl-01-cam0-rgb",
}


def main():
    total_frames = 0

    for name, folder in SEQUENCES.items():
        images = sorted(
            folder.glob("*.png"),
            key=lambda path: int(path.stem.rsplit("-", 1)[-1])
        )

        if not images:
            print(f"[ERROR] No PNG images found: {folder}")
            continue

        readable = 0
        dimensions = set()

        for image_path in images:
            frame = cv2.imread(str(image_path))

            if frame is not None:
                readable += 1
                height, width = frame.shape[:2]
                dimensions.add((width, height))

        total_frames += readable

        print(f"\n{name}")
        print(f"  Folder: {folder}")
        print(f"  Image files: {len(images)}")
        print(f"  Readable images: {readable}")
        print(f"  Image dimensions (width, height): {sorted(dimensions)}")

        if readable != len(images):
            print("  WARNING: Some images could not be read.")

    print(f"\nTotal readable frames: {total_frames}")


if __name__ == "__main__":
    main()
