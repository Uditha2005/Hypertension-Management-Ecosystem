"""Convert the local single-pill COCO exports into a YOLO detection dataset."""

import hashlib
import json
import math
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from PIL import Image


COMPONENT = Path(__file__).resolve().parents[1]
SOURCE = COMPONENT / "data" / "My_Dataset"
OUTPUT = COMPONENT / "data" / "local_medicines_yolo"
SEED = 42


def class_name(folder):
    # Preserve source naming until names are verified against packaging.
    if folder.casefold() in {
        "losartan 50mg white",
        "losartan 50mg yellow",
    }:
        return "Losartan 50mg"
    return folder.strip()


def main():
    if not SOURCE.is_dir():
        raise SystemExit(f"Dataset folder missing: {SOURCE}")

    if OUTPUT.exists():
        raise SystemExit(
            f"Output already exists: {OUTPUT}\n"
            "Rename that output folder before running again."
        )

    json_files = sorted(SOURCE.rglob("_annotations.coco.json"))
    if not json_files:
        raise SystemExit("No _annotations.coco.json files found.")

    records = []
    review = []
    hashes = {}
    errors = []

    for json_path in json_files:
        folder = json_path.relative_to(SOURCE).parts[0]
        label = class_name(folder)
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))

        images = {item["id"]: item for item in data["images"]}
        categories = {item["id"] for item in data["categories"]}
        annotations = defaultdict(list)

        for annotation in data["annotations"]:
            if annotation["image_id"] not in images:
                errors.append(f"{json_path}: unknown image ID")
                continue
            if annotation["category_id"] not in categories:
                errors.append(f"{json_path}: unknown category ID")
                continue
            annotations[annotation["image_id"]].append(annotation)

        for image_id, info in images.items():
            image_path = json_path.parent / info["file_name"]

            if not image_path.is_file():
                errors.append(f"Missing photo: {image_path}")
                continue

            boxes = annotations[image_id]

            # The supplied dataset is explicitly one pill per photo.
            # Do not guess which overlapping annotation is correct.
            if len(boxes) != 1:
                review.append({
                    "image": str(image_path.relative_to(SOURCE)),
                    "reason": f"Expected 1 box, found {len(boxes)}",
                })
                continue

            with Image.open(image_path) as image:
                width, height = image.size
                image.verify()

            if width != info["width"] or height != info["height"]:
                errors.append(f"Image/annotation dimensions differ: {image_path}")
                continue

            box = boxes[0].get("bbox", [])
            if (
                len(box) != 4
                or any(
                    not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in box
                )
            ):
                errors.append(f"Invalid box: {image_path}")
                continue

            x, y, w, h = box
            tolerance = 1.0

            if (
                w <= 0 or h <= 0
                or x < -tolerance or y < -tolerance
                or x + w > width + tolerance
                or y + h > height + tolerance
            ):
                errors.append(f"Box outside photo: {image_path}")
                continue

            # Clip only minor rounding at image edges.
            right = min(width, x + w)
            bottom = min(height, y + h)
            x, y = max(0, x), max(0, y)
            w, h = right - x, bottom - y

            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if digest in hashes:
                if hashes[digest] != label:
                    errors.append(f"Identical photo has conflicting classes: {image_path}")
                else:
                    review.append({
                        "image": str(image_path.relative_to(SOURCE)),
                        "reason": "Identical photo already included",
                    })
                continue
            hashes[digest] = label

            # Keep Roboflow variants of the same original in one split.
            original = re.split(r"\.rf\.", image_path.stem)[0]
            group = (folder, original)

            records.append({
                "path": image_path,
                "class": label,
                "folder": folder,
                "group": group,
                "digest": digest,
                "box": [
                    (x + w / 2) / width,
                    (y + h / 2) / height,
                    w / width,
                    h / height,
                ],
            })

    if errors:
        print("Fix these issues before conversion:")
        for error in errors[:30]:
            print("-", error)
        raise SystemExit(f"Stopped: {len(errors)} issue(s). No output created.")

    if not records:
        raise SystemExit("No usable annotated photos found.")

    names = sorted({record["class"] for record in records})
    class_ids = {name: index for index, name in enumerate(names)}

    # Split each source folder separately so both Losartan appearances
    # are represented. Original-image variants remain together.
    by_folder = defaultdict(lambda: defaultdict(list))
    for record in records:
        by_folder[record["folder"]][record["group"]].append(record)

    assignments = []
    rng = random.Random(SEED)

    for folder, groups in sorted(by_folder.items()):
        keys = sorted(groups)
        if len(keys) < 10:
            raise SystemExit(f"Too few original photo groups: {folder}")

        rng.shuffle(keys)
        test_count = max(1, round(len(keys) * 0.15))
        val_count = max(1, round(len(keys) * 0.15))

        for index, key in enumerate(keys):
            split = (
                "test" if index < test_count
                else "val" if index < test_count + val_count
                else "train"
            )
            for record in groups[key]:
                assignments.append((split, record))

    for split in ("train", "val", "test"):
        (OUTPUT / "images" / split).mkdir(parents=True)
        (OUTPUT / "labels" / split).mkdir(parents=True)

    manifest = []
    counts = Counter()

    for split, record in assignments:
        class_id = class_ids[record["class"]]
        stem = f"c{class_id:02d}_{record['digest'][:20]}"
        suffix = record["path"].suffix.lower()

        shutil.copy2(
            record["path"],
            OUTPUT / "images" / split / f"{stem}{suffix}",
        )

        values = " ".join(f"{value:.8f}" for value in record["box"])
        (OUTPUT / "labels" / split / f"{stem}.txt").write_text(
            f"{class_id} {values}\n", encoding="utf-8"
        )

        counts[split] += 1
        manifest.append({
            "source": str(record["path"].relative_to(SOURCE)),
            "split": split,
            "classId": class_id,
            "className": record["class"],
            "sha256": record["digest"],
        })

    configuration = {
        "path": OUTPUT.resolve().as_posix(),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(names)),
    }
    (OUTPUT / "data.yaml").write_text(
        yaml.safe_dump(configuration, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    for filename, payload in (
        ("manifest.json", manifest),
        ("review_required.json", review),
    ):
        (OUTPUT / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print("\nDATASET READY")
    print("Classes:", len(names))
    print("Photos:", len(manifest))
    print("Splits:", dict(counts))
    print("Excluded for review:", len(review))
    print("Configuration:", OUTPUT / "data.yaml")

    print("\nCLASS NAMES — verify against the medicine packaging:")
    for index, name in enumerate(names):
        print(f"{index}: {name}")

    print("\nExcluded photos:")
    for item in review:
        print(item["reason"], "->", item["image"])


if __name__ == "__main__":
    main()