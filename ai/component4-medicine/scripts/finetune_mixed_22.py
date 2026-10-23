"""Add the annotated mixed tray and fine-tune a separate 22-class model."""

import argparse
import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml
from PIL import Image
from ultralytics import YOLO


COMPONENT = Path(__file__).resolve().parents[1]
BASE = COMPONENT / "data" / "local_medicines_yolo_v2"
SOURCE = COMPONENT / "data" / "mixed_trays_oct23"
OUTPUT = COMPONENT / "data" / "local_medicines_yolo_v3"
CHECKPOINT = COMPONENT / "models" / "local_medicines_best.pt"
RUNS = COMPONENT / "runs" / "local_medicines"

MAPPING = {
    "Amlodipine 5mg": "Amlodipine 5mg",
    "Diltiazem 90mg": "Diltiazem 90mg",
    "Irbesartan 150mg": "Irbesartan_Irovel_150mg",
    "Losartan 50mg": "Losartan 50mg",
    "Telmisartan 40mg": "Telmisartan (Telsart)",
}

NEW_CLASSES = ["Amlodipine 5mg", "Diltiazem 90mg"]
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_names(config):
    names = config["names"]
    if isinstance(names, list):
        return list(names)

    indexed = {int(key): str(value) for key, value in names.items()}
    if sorted(indexed) != list(range(len(indexed))):
        raise ValueError("Dataset class IDs must be consecutive.")
    return [indexed[index] for index in range(len(indexed))]


def checkpoint_names(model):
    names = model.names
    if isinstance(names, dict):
        return [str(names[index]) for index in range(len(names))]
    return list(names)


def find_photo(json_path, filename):
    relative = Path(filename.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe image path: {filename}")

    direct = json_path.parent / relative
    if direct.is_file():
        return direct

    matches = list(json_path.parent.rglob(relative.name))
    if len(matches) != 1:
        raise ValueError(f"Cannot uniquely find image: {filename}")
    return matches[0]


def prepare():
    config_path = BASE / "data.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"Dataset configuration missing: {config_path}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    old_names = read_names(config)

    if len(old_names) != 20:
        raise ValueError("Expected the original 20-class dataset.")

    for name in MAPPING.values():
        if name not in old_names and name not in NEW_CLASSES:
            raise ValueError(f"Mapping target missing: {name}")

    names = old_names + NEW_CLASSES
    json_files = sorted(SOURCE.rglob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No COCO JSON files found in {SOURCE}")

    existing_hashes = set()
    for split in ("train", "val", "test"):
        folder = BASE / "images" / split
        if not folder.is_dir():
            raise FileNotFoundError(f"Missing image folder: {folder}")
        for photo in folder.rglob("*"):
            if photo.is_file() and photo.suffix.lower() in IMAGE_TYPES:
                existing_hashes.add(digest(photo))

    prepared = []
    added_hashes = set()
    class_counts = Counter()

    for json_path in json_files:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        categories = {
            item["id"]: item["name"]
            for item in data.get("categories", [])
        }
        annotations = {}
        images = data.get("images", [])
        image_ids = [item["id"] for item in images]

        if len(image_ids) != len(set(image_ids)):
            raise ValueError(f"Duplicate image IDs in {json_path}")

        for annotation in data.get("annotations", []):
            image_id = annotation["image_id"]
            if image_id not in image_ids:
                raise ValueError("Annotation refers to a missing image.")
            annotations.setdefault(image_id, []).append(annotation)

        for item in images:
            photo = find_photo(json_path, item["file_name"])
            photo_hash = digest(photo)

            if photo_hash in existing_hashes:
                raise ValueError(
                    f"Photo already exists in the base dataset: {photo.name}. "
                    "Check its existing split and annotations before merging."
                )
            if photo_hash in added_hashes:
                raise ValueError(f"Duplicate new photo: {photo.name}")
            added_hashes.add(photo_hash)

            with Image.open(photo) as image:
                width, height = image.size
                image.verify()

            if (width, height) != (item["width"], item["height"]):
                raise ValueError(f"COCO image dimensions differ: {photo.name}")

            boxes = annotations.get(item["id"], [])
            if not boxes:
                raise ValueError(f"No annotations found: {photo.name}")

            labels = []
            for annotation in boxes:
                if annotation.get("iscrowd", 0):
                    raise ValueError("Crowd annotations need separate review.")

                source_name = categories.get(annotation["category_id"])
                if source_name not in MAPPING:
                    raise ValueError(
                        f"Unmapped annotated class: {source_name}"
                    )

                bbox = annotation.get("bbox")
                if (
                    not isinstance(bbox, list)
                    or len(bbox) != 4
                    or any(
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        for value in bbox
                    )
                ):
                    raise ValueError(f"Invalid bounding box: {photo.name}")

                x, y, box_width, box_height = bbox
                if (
                    x < 0
                    or y < 0
                    or box_width <= 0
                    or box_height <= 0
                    or x + box_width > width
                    or y + box_height > height
                ):
                    raise ValueError(f"Box outside image: {photo.name}")

                target_name = MAPPING[source_name]
                class_id = names.index(target_name)

                center_x = (x + box_width / 2) / width
                center_y = (y + box_height / 2) / height

                labels.append(
                    f"{class_id} "
                    f"{center_x:.8f} {center_y:.8f} "
                    f"{box_width / width:.8f} "
                    f"{box_height / height:.8f}"
                )
                class_counts[target_name] += 1

            prepared.append((photo, photo_hash, labels))

    if not prepared:
        raise ValueError("No annotated images found.")

    manifest = {
        "baseDataset": str(BASE),
        "classes": names,
        "mapping": MAPPING,
        "newImages": sorted(added_hashes),
        "newBoxes": dict(sorted(class_counts.items())),
        "addedTo": "train",
    }

    manifest_path = OUTPUT / "mixed_merge_manifest.json"

    if OUTPUT.exists():
        if (
            not manifest_path.is_file()
            or json.loads(manifest_path.read_text(encoding="utf-8"))
            != manifest
        ):
            raise ValueError(
                "Output folder already exists with different contents. "
                "Keep it intact and choose another OUTPUT folder."
            )
        if not (OUTPUT / "data.yaml").is_file():
            raise ValueError("Existing output configuration is missing.")
        print("Existing matching prepared dataset reused.")
        return OUTPUT / "data.yaml", old_names

    staging = Path(
        tempfile.mkdtemp(prefix="mixed22_", dir=OUTPUT.parent)
    )
    try:
        shutil.copytree(BASE, staging, dirs_exist_ok=True)

        # Remove dataset caches copied from the 20-class configuration.
        for cache in staging.rglob("*.cache"):
            cache.unlink()

        image_folder = staging / "images" / "train"
        label_folder = staging / "labels" / "train"
        image_folder.mkdir(parents=True, exist_ok=True)
        label_folder.mkdir(parents=True, exist_ok=True)

        for photo, photo_hash, labels in prepared:
            stem = "mixed_oct23_" + photo_hash
            shutil.copy2(
                photo,
                image_folder / (stem + photo.suffix.lower()),
            )
            (label_folder / (stem + ".txt")).write_text(
                "\n".join(labels) + "\n",
                encoding="utf-8",
            )

        new_config = {
            "path": str(OUTPUT.resolve()),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test",
            "names": dict(enumerate(names)),
        }

        (staging / "data.yaml").write_text(
            yaml.safe_dump(new_config, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        (staging / "mixed_merge_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        staging.rename(OUTPUT)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    print("\nDATASET READY")
    print("Classes:", len(names))
    print("New mixed photos:", len(prepared))
    print("New boxes:", sum(class_counts.values()))
    for name, count in sorted(class_counts.items()):
        print(f"  {name}: {count}")
    print("Configuration:", OUTPUT / "data.yaml")
    print("Original train/validation/test files preserved.")
    print("New photos added to TRAIN only.")

    return OUTPUT / "data.yaml", old_names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()

    data_yaml, old_names = prepare()

    if not args.train:
        print("\nPreparation complete. Use --train to start fine-tuning.")
        return

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA unavailable. Run with the .venv-train Python environment."
        )
    if not CHECKPOINT.is_file():
        raise FileNotFoundError(f"Checkpoint missing: {CHECKPOINT}")

    model = YOLO(str(CHECKPOINT))
    if model.task != "detect" or checkpoint_names(model) != old_names:
        raise ValueError(
            "Checkpoint classes/order do not match the base dataset."
        )

    run_name = "mixed_22_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\nStarting a NEW fine-tuning run with 22 classes.")
    print("Compatible checkpoint weights will transfer.")
    print("The changed detection head requires further training.")
    print("Validation does not measure the two new classes yet.")

    model.train(
        data=str(data_yaml),
        project=str(RUNS),
        name=run_name,
        epochs=50,
        patience=15,
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        optimizer="AdamW",
        lr0=0.0001,
        seed=42,
        amp=True,
        cache=False,
        plots=True,
        save=True,
        resume=False,
    )

    save_dir = Path(model.trainer.save_dir).resolve()
    best = save_dir / "weights" / "best.pt"

    if not best.is_file():
        raise RuntimeError("Training ended without a best checkpoint.")

    record = {
        "bestCheckpoint": str(best),
        "dataset": str(data_yaml),
        "runDirectory": str(save_dir),
        "classCount": 22,
        "validationCoverage": "Original 20 classes only",
        "websiteCheckpointReplaced": False,
    }

    record_path = RUNS / "latest_mixed_22_training.json"
    record_path.write_text(
        json.dumps(record, indent=2),
        encoding="utf-8",
    )

    print("\nTRAINING FINISHED")
    print("Best checkpoint:", best)
    print("Record:", record_path)
    print("Website checkpoint has NOT been replaced.")


if __name__ == "__main__":
    main()