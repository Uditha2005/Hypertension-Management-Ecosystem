"""Merge reviewed mixed-tray COCO images into a COPY of the 22-class dataset.

Old split membership/class IDs are preserved. Website weights are never replaced.
"""
import argparse
import gc
import hashlib
import io
import json
import math
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path, PurePosixPath

import yaml
from PIL import Image

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ALIASES = {
    "Carvedilol 3.125mg": "Carvedilil -3-125mg",
    "Clopidogrel 75mg": "Clopidogrel -clopact- 75mg",
    "Irbesartan 150mg": "Irbesartan_Irovel_150mg",
    "Nitedipine 20mg": "Nitedipine -Nicardia E 20mg",
}


def names_list(names):
    if isinstance(names, dict):
        keys = {int(k): str(v) for k, v in names.items()}
        if sorted(keys) != list(range(len(keys))):
            raise ValueError("Class IDs must be contiguous from zero.")
        return [keys[i] for i in range(len(keys))]
    if isinstance(names, list) and all(isinstance(n, str) for n in names):
        return names
    raise ValueError("Invalid dataset/model class names.")


def image_hash(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 20_000_000:
            raise ValueError("Image exceeds 20 megapixels.")
        with image.convert("RGB") as rgb:
            digest = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
            return digest, rgb.size


def check_labels(text, class_count):
    labels = []
    for line in text.splitlines():
        if not line.strip():
            continue
        values = [float(v) for v in line.split()]
        if len(values) != 5 or not all(math.isfinite(v) for v in values):
            raise ValueError("Expected YOLO detection rows: class cx cy width height.")
        cid, x, y, w, h = values
        if not cid.is_integer() or not 0 <= cid < class_count:
            raise ValueError("Invalid YOLO class ID.")
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            raise ValueError("Invalid normalized YOLO bounding box.")
        if x-w/2 < -1e-4 or y-h/2 < -1e-4 or x+w/2 > 1.0001 or y+h/2 > 1.0001:
            raise ValueError("YOLO box extends outside the image.")
        labels.append((int(cid), x, y, w, h))
    return sorted(labels)


def labels_equal(a, b):
    return len(a) == len(b) and all(
        first[0] == second[0] and all(abs(x-y) <= 1e-4 for x, y in zip(first[1:], second[1:]))
        for first, second in zip(sorted(a), sorted(b))
    )


def label_text(labels):
    return "".join(f"{cid} {x:.8f} {y:.8f} {w:.8f} {h:.8f}\n" for cid, x, y, w, h in labels)


def scan_base(yaml_path, expected_names):
    spec = yaml.safe_load(yaml_path.read_text(encoding="utf-8-sig"))
    if names_list(spec["names"]) != expected_names:
        raise ValueError("Base dataset class names/order differ from the checkpoint. No training started.")
    root = Path(spec.get("path") or yaml_path.parent)
    if not root.is_absolute():
        root = (yaml_path.parent / root).resolve()
    records, seen = [], {}
    for split in ("train", "val", "test"):
        value = spec.get(split)
        if not value and split == "test":
            continue
        if not isinstance(value, str):
            raise ValueError(f"Expected a single image directory for {split}.")
        folder = Path(value)
        if not folder.is_absolute():
            folder = root / folder
        if not folder.is_dir():
            raise ValueError(f"Image directory missing: {folder}")
        photos = sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_TYPES)
        if not photos:
            raise ValueError(f"No images in {folder}")
        for photo in photos:
            relative = photo.relative_to(folder)
            label_path = root / "labels" / split / relative.with_suffix(".txt")
            if not label_path.is_file():
                raise ValueError(f"Label file missing: {label_path}")
            text = label_path.read_text(encoding="utf-8-sig")
            labels = check_labels(text, len(expected_names))
            digest, size = image_hash(photo.read_bytes())
            if digest in seen:
                previous = seen[digest]
                if previous["split"] != split:
                    raise ValueError(f"Existing train/validation/test image leakage: {photo}")
                if not labels_equal(previous["labels"], labels):
                    raise ValueError(f"Existing identical photo has conflicting labels: {photo}")
            record = dict(split=split, source=photo, labels=labels, label_text=text, digest=digest, size=size)
            records.append(record)
            seen[digest] = record
    return records, seen


def read_coco(zip_path, class_names, existing):
    output, skipped, seen = [], [], {}
    lookup = {name: i for i, name in enumerate(class_names)}
    with zipfile.ZipFile(zip_path) as archive:
        json_files = [n for n in archive.namelist() if n.endswith("_annotations.coco.json")]
        if len(json_files) != 1:
            raise ValueError("Expected the reviewed ZIP with one COCO annotation file.")
        json_path = json_files[0]
        data = json.loads(archive.read(json_path))
        categories = {c["id"]: c["name"] for c in data["categories"]}
        images = {im["id"]: im for im in data["images"]}
        if len(images) != len(data["images"]):
            raise ValueError("Duplicate COCO image IDs.")
        grouped = defaultdict(list)
        annotation_ids = set()
        for annotation in data["annotations"]:
            if annotation["id"] in annotation_ids:
                raise ValueError("Duplicate COCO annotation IDs.")
            annotation_ids.add(annotation["id"])
            if annotation["image_id"] not in images or annotation["category_id"] not in categories:
                raise ValueError("COCO annotation references a missing image/category.")
            grouped[annotation["image_id"]].append(annotation)
        mapping = {}
        for image_id, image in images.items():
            filename = image["file_name"]
            if "11-19-28-PM-1-" in filename:
                raise ValueError("The excluded photo is still in this ZIP. Select traysDB-cleaned.v1i.coco.zip.")
            path = PurePosixPath(filename)
            if path.is_absolute() or ".." in path.parts or path.suffix.lower() not in IMAGE_TYPES:
                raise ValueError("Invalid image path in archive.")
            member = str(PurePosixPath(json_path).parent / path)
            info = archive.getinfo(member)
            if info.file_size > 30_000_000:
                raise ValueError("Archived image is too large.")
            content = archive.read(member)
            digest, size = image_hash(content)
            if size != (image["width"], image["height"]):
                raise ValueError(f"COCO dimensions differ from actual image: {filename}")
            width, height = size
            labels = []
            for annotation in grouped[image_id]:
                original = categories[annotation["category_id"]]
                target = ALIASES.get(original, original)
                if target not in lookup:
                    raise ValueError(f"Unknown class: {original}. No automatic class append/renumbering allowed.")
                mapping[original] = target
                box = annotation["bbox"]
                if len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
                    raise ValueError(f"Invalid COCO box: {filename}")
                x, y, w, h = box
                if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > width+1e-6 or y+h > height+1e-6 or annotation.get("iscrowd", 0):
                    raise ValueError(f"Invalid/out-of-bounds/crowd box: {filename}")
                labels.append((lookup[target], (x+w/2)/width, (y+h/2)/height, w/width, h/height))
            if not labels:
                raise ValueError(f"Mixed tray image has no labels: {filename}")
            labels.sort()
            previous = existing.get(digest) or seen.get(digest)
            if previous:
                if not labels_equal(previous["labels"], labels):
                    raise ValueError(f"Identical photo has different annotations: {filename}. Review labels before training.")
                skipped.append(dict(filename=filename, reason="Already present", split=previous.get("split", "new-train")))
                continue
            record = dict(filename=filename, content=content, digest=digest, labels=labels, size=size)
            output.append(record)
            seen[digest] = record
    if not output:
        raise ValueError("No new unique mixed-tray photos to add.")
    return output, skipped, mapping


def prepare_dataset(base_yaml, zip_path, names, destination, mixed_repeat):
    # Finish all audits before creating the new dataset directory.
    base, hashes = scan_base(base_yaml, names)
    mixed, skipped, mapping = read_coco(zip_path, names, hashes)
    if destination.exists():
        raise ValueError("Output dataset already exists; refusing to overwrite it.")
    destination.mkdir(parents=True)
    counts = Counter()
    for index, record in enumerate(base):
        split = record["split"]
        stem = f"base_{index:06d}"
        photo = destination / "images" / split / (stem + record["source"].suffix.lower())
        label = destination / "labels" / split / (stem + ".txt")
        photo.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(record["source"], photo)
        label.write_text(record["label_text"], encoding="utf-8")
        counts[split] += 1
    for index, record in enumerate(mixed):
        for repeat in range(mixed_repeat):
            stem = f"tray_{index:03d}_{record['digest'][:12]}_repeat{repeat}"
            photo = destination / "images/train" / (stem + PurePosixPath(record["filename"]).suffix.lower())
            label = destination / "labels/train" / (stem + ".txt")
            photo.write_bytes(record["content"])
            label.write_text(label_text(record["labels"]), encoding="utf-8")
            counts["train"] += 1
    configuration = {"path": str(destination.resolve()), "train": "images/train", "val": "images/val", "names": dict(enumerate(names))}
    if counts["test"]:
        configuration["test"] = "images/test"
    yaml_path = destination / "data.yaml"
    yaml_path.write_text(yaml.safe_dump(configuration, sort_keys=False, allow_unicode=True), encoding="utf-8")
    manifest = {
        "baseYaml": str(base_yaml.resolve()), "mixedZip": str(zip_path.resolve()),
        "sourceZipSHA256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "classNames": names, "classMapping": mapping, "baseCounts": dict(Counter(r["split"] for r in base)),
        "newUniquePhotos": len(mixed), "newUniqueBoxes": sum(len(r["labels"]) for r in mixed),
        "mixedRepeat": mixed_repeat, "addedTrainingCopies": len(mixed)*mixed_repeat,
        "outputCounts": dict(counts), "skippedDuplicates": skipped,
        "newPhotos": [{"filename": r["filename"], "sha256Pixels": r["digest"], "labels": r["labels"]} for r in mixed],
        "evaluationNote": "Original val/test membership preserved. Mixed repeats are weighting only, not independent new samples. New trays are training data, not a held-out accuracy test.",
    }
    (destination / "merge_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return yaml_path, manifest


def evaluate(checkpoint, yaml_path, folder, name, batch):
    from ultralytics import YOLO
    import torch
    model = YOLO(str(checkpoint))
    metrics = model.val(data=str(yaml_path), split="val", imgsz=640, batch=batch, device=0,
                        workers=0, conf=0.001, iou=0.7, plots=False,
                        project=str(folder), name=name, exist_ok=False)
    result = {"precision": float(metrics.box.mp), "recall": float(metrics.box.mr),
              "mAP50": float(metrics.box.map50), "mAP50_95": float(metrics.box.map)}
    del model, metrics
    gc.collect()
    torch.cuda.empty_cache()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--mixed-repeat", type=int, default=4)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.epochs <= 300 or not 1 <= args.mixed_repeat <= 10:
        raise ValueError("Invalid epochs or training repeat count.")
    import torch
    from ultralytics import YOLO
    component = args.component.resolve()
    base = component / "data/local_medicines_yolo_v3/data.yaml"
    checkpoint = component / "models/local_medicines_best.pt"
    for path in (args.zip, base, checkpoint):
        if not path.is_file():
            raise FileNotFoundError(str(path))
    if not args.prepare_only and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable. Run with the project's .venv-train Python.")
    model = YOLO(str(checkpoint))
    names = names_list(model.names)
    if model.task != "detect" or len(names) != 22:
        raise ValueError("Expected the current 22-class detection checkpoint.")
    del model
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dataset = component / "data" / ("local_trays_oct25_" + stamp)
    yaml_path, manifest = prepare_dataset(base, args.zip.resolve(), names, dataset, args.mixed_repeat)
    print("\nDATASET READY", flush=True)
    print("Classes:", len(names), "(original order preserved)", flush=True)
    print("New unique photos:", manifest["newUniquePhotos"], "New unique boxes:", manifest["newUniqueBoxes"], flush=True)
    print("Mixed-tray training weighting:", args.mixed_repeat, "copies per photo (not new independent data)", flush=True)
    print("Split sizes:", manifest["outputCounts"], flush=True)
    print("Configuration:", yaml_path, flush=True)
    print("Class mapping:", json.dumps(manifest["classMapping"], indent=2), flush=True)
    if args.prepare_only:
        return
    torch.set_num_threads(4)
    print("GPU:", torch.cuda.get_device_name(0), flush=True)
    runs = component / "runs/local_medicines"
    run_name = "trays_oct25_" + stamp
    run_folder = runs / run_name
    evaluation_folder = runs / (run_name + "_evaluation")
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    before = evaluate(checkpoint, yaml_path, evaluation_folder, "before", 2)
    model = YOLO(str(checkpoint))
    model.train(data=str(yaml_path), epochs=args.epochs, imgsz=640, batch=2,
                device=0, workers=0, cache=False, amp=True, resume=False,
                optimizer="AdamW", lr0=0.0005, lrf=0.1, warmup_epochs=3,
                patience=20, seed=42, deterministic=True,
                degrees=20, translate=0.1, scale=0.3,
                fliplr=0.0, flipud=0.0, hsv_h=0.01, hsv_s=0.2, hsv_v=0.2,
                mosaic=0.5, close_mosaic=5, mixup=0.0,
                save=True, save_period=10, plots=True,
                project=str(runs), name=run_name, exist_ok=False)
    actual_folder = Path(model.trainer.save_dir)
    best = actual_folder / "weights/best.pt"
    last = actual_folder / "weights/last.pt"
    del model
    gc.collect()
    torch.cuda.empty_cache()
    if not best.is_file():
        raise RuntimeError("Training ended without best.pt; inspect the training output.")
    after = evaluate(best, yaml_path, evaluation_folder, "after", 2)
    record = dict(bestCheckpoint=str(best.resolve()), lastCheckpoint=str(last.resolve()),
                  sourceCheckpoint=str(checkpoint), sourceCheckpointSHA256=checkpoint_hash,
                  datasetYaml=str(yaml_path), classNames=names, beforeValidation=before,
                  afterValidation=after, modelDeployed=False, newUniquePhotos=manifest["newUniquePhotos"],
                  note="Val set is the existing dataset's validation split. The eight added trays were used in training and cannot establish unseen-tray accuracy.")
    record_path = runs / "latest_trays_oct25_training.json"
    (actual_folder / "training_record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != checkpoint_hash:
        raise RuntimeError("The deployed checkpoint changed externally during training. Inspect it before continuing.")
    print("\nTRAINING FINISHED", flush=True)
    print("Best checkpoint:", best, flush=True)
    print("Last checkpoint:", last, flush=True)
    print("Record:", record_path, flush=True)
    print("BEFORE VALIDATION:", json.dumps(before), flush=True)
    print("AFTER VALIDATION:", json.dumps(after), flush=True)
    print("Website checkpoint was NOT replaced. Test new, independently captured trays before deploying.", flush=True)


if __name__ == "__main__":
    main()
