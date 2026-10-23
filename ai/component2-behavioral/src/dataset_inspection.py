
from pathlib import Path
import cv2

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_sequences():
    sequences = []

    # Fall sequences: Camera 0 and Camera 1
    fall_dir = DATA_DIR / "fall"
    if fall_dir.exists():
        for folder in sorted(fall_dir.glob("fall-*-cam*-rgb")):
            sequences.append((f"Fall - {folder.name}", folder))

    # Normal ADL sequences: available camera folders
    normal_dir = DATA_DIR / "normal"
    if normal_dir.exists():
        for folder in sorted(normal_dir.glob("adl-*-cam*-rgb")):
            sequences.append((f"Normal ADL - {folder.name}", folder))

    return sequences


def main():
    total_frames = 0
    total_images = 0
    total_sequences = 0

    for name, folder in get_sequences():
        images = sorted(
            folder.glob("*.png"),
            key=lambda path: (
                int(path.stem.rsplit("-", 1)[-1])
                if path.stem.rsplit("-", 1)[-1].isdigit()
                else path.stem
            )
        )

        if not images:
            print(f"[WARNING] No PNG images found: {folder}")
            continue

        readable = 0
        dimensions = set()

        for image_path in images:
            frame = cv2.imread(str(image_path))

            if frame is not None:
                readable += 1
                height, width = frame.shape[:2]
                dimensions.add((width, height))

        total_sequences += 1
        total_images += len(images)
        total_frames += readable

        print(f"\n{name}")
        print(f"  Folder: {folder}")
        print(f"  Image files: {len(images)}")
        print(f"  Readable images: {readable}")
        print(f"  Image dimensions (width, height): {sorted(dimensions)}")

        if readable != len(images):
            print("  WARNING: Some images could not be read.")

    print("\n========== DATASET SUMMARY ==========")
    print(f"Total sequences: {total_sequences}")
    print(f"Total image files: {total_images}")
    print(f"Total readable frames: {total_frames}")


if __name__ == "__main__":
    main()
