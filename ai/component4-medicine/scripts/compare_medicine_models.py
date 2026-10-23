"""Compare three medicine detector candidates using validation metrics.

Uses the original local dataset, before the mixed-photo addition.
Does not modify the website checkpoint or evaluate the test split.
"""

import csv
import gc
import json
from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path

import torch
import ultralytics
import yaml
from ultralytics import YOLO


COMPONENT = Path(__file__).resolve().parents[1]

DATASET = COMPONENT / "data/local_medicines_yolo/data.yaml"

BASELINE = (
    COMPONENT
    / "runs/local_medicines/mediseg_finetune/weights/best.pt"
)

COMMON_TRAINING = {
    "epochs": 100,
    "patience": 20,
    "imgsz": 640,
    "batch": 2,
    "device": 0,
    "workers": 0,
    "amp": True,
    "cache": False,
    "optimizer": "AdamW",
    "lr0": 0.001,
    "seed": 42,
    "deterministic": True,
    "save": True,
    "plots": True,
    "close_mosaic": 10,
}

FIELDS = [
    "model",
    "pretraining",
    "precision_percent",
    "recall_percent",
    "map50_percent",
    "map50_95_percent",
    "parameters",
    "checkpoint_mb",
    "validation_inference_ms",
    "checkpoint",
    "validation_directory",
]


def ordered_names(names):
    if isinstance(names, dict):
        converted = {int(key): value for key, value in names.items()}
        return [converted[index] for index in range(len(converted))]
    return list(names)


def write_results(folder, rows):
    with (folder / "comparison.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    (folder / "comparison.json").write_text(
        json.dumps(rows, indent=2),
        encoding="utf-8",
    )


def evaluate(label, pretraining, checkpoint, folder, expected_names):
    model = YOLO(str(checkpoint))

    if ordered_names(model.names) != expected_names:
        raise ValueError(f"Class order mismatch: {label}")

    parameters = sum(
        parameter.numel()
        for parameter in model.model.parameters()
    )

    metrics = model.val(
        data=str(DATASET),
        split="val",
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        conf=0.001,
        iou=0.7,
        max_det=300,
        agnostic_nms=False,
        augment=False,
        half=False,
        plots=True,
        project=str(folder),
        name=label + "_validation",
        exist_ok=False,
    )

    row = {
        "model": label,
        "pretraining": pretraining,
        "precision_percent": round(float(metrics.box.mp) * 100, 4),
        "recall_percent": round(float(metrics.box.mr) * 100, 4),
        "map50_percent": round(float(metrics.box.map50) * 100, 4),
        "map50_95_percent": round(float(metrics.box.map) * 100, 4),
        "parameters": parameters,
        "checkpoint_mb": round(
            checkpoint.stat().st_size / (1024 * 1024), 3
        ),
        "validation_inference_ms": round(
            float(metrics.speed.get("inference", 0)), 4
        ),
        "checkpoint": str(checkpoint.resolve()),
        "validation_directory": str(Path(metrics.save_dir).resolve()),
    }

    del metrics, model
    gc.collect()
    torch.cuda.empty_cache()

    return row


def main():
    if not DATASET.is_file():
        raise SystemExit(f"Original dataset missing: {DATASET}")

    if not BASELINE.is_file():
        raise SystemExit(
            "Original fine-tuned YOLOv8n checkpoint missing:\n"
            f"{BASELINE}\n"
            "Do not substitute the mixed-photo checkpoint."
        )

    if not torch.cuda.is_available():
        raise SystemExit(
            "CUDA unavailable. Run with the .venv-train interpreter."
        )

    config = yaml.safe_load(
        DATASET.read_text(encoding="utf-8-sig")
    )
    expected_names = ordered_names(config["names"])

    if len(expected_names) != 20:
        raise SystemExit("Expected the original 20-class dataset.")

    dataset_root = Path(config.get("path", DATASET.parent))
    if not dataset_root.is_absolute():
        dataset_root = (DATASET.parent / dataset_root).resolve()

    for split in ("train", "val"):
        split_value = config.get(split)
        if not isinstance(split_value, str):
            raise SystemExit(f"Expected one directory for {split}.")

        split_path = Path(split_value)
        if not split_path.is_absolute():
            split_path = dataset_root / split_path

        if not split_path.is_dir():
            raise SystemExit(f"Split directory missing: {split_path}")

    folder = (
        COMPONENT
        / "runs/model_comparison"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    folder.mkdir(parents=True, exist_ok=False)

    alternatives = [
        ("YOLOv5nu", "yolov5nu.pt"),
        ("YOLO11n", "yolo11n.pt"),
    ]

    # Download/load both starting checkpoints before lengthy training.
    prepared_weights = {}
    for label, weight_name in alternatives:
        print(f"\nPreparing {label} starting checkpoint...")
        model = YOLO(weight_name)

        if model.task != "detect":
            raise ValueError(f"{label} is not a detection model.")

        prepared_weights[label] = str(
            Path(model.ckpt_path).resolve()
        )
        del model
        gc.collect()

    metadata = {
        "dataset": str(DATASET),
        "datasetConfiguration": config,
        "baselineCheckpoint": str(BASELINE),
        "alternativeStartingWeights": prepared_weights,
        "commonAlternativeTraining": COMMON_TRAINING,
        "selectionMetric": "validation mAP50-95",
        "evaluationSplit": "val",
        "ultralytics": ultralytics.__version__,
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
        "limitations": [
            "YOLOv8n had MEDISEG pretraining; alternatives use COCO.",
            "Baseline is reused from the earlier training run.",
            "Single seed comparison; variation across seeds is not measured.",
            "Validation timing is indicative, not a deployment benchmark.",
            "Test split is not evaluated by this script.",
            "Multiscale website fusion is not evaluated here.",
        ],
    }

    (folder / "experiment.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print("\nGPU:", metadata["gpu"])
    print("Experiment directory:", folder)

    rows = []

    print("\nEvaluating existing YOLOv8n baseline...")
    rows.append(evaluate(
        "YOLOv8n_MEDISEG",
        "MEDISEG then local fine-tuning",
        BASELINE,
        folder,
        expected_names,
    ))
    write_results(folder, rows)

    for label, _ in alternatives:
        print(f"\nTraining {label}...")
        model = YOLO(prepared_weights[label])

        model.train(
            data=str(DATASET),
            project=str(folder),
            name=label + "_training",
            exist_ok=False,
            **COMMON_TRAINING,
        )

        checkpoint = (
            Path(model.trainer.save_dir).resolve()
            / "weights/best.pt"
        )

        if not checkpoint.is_file():
            raise RuntimeError(f"No best checkpoint produced: {label}")

        del model
        gc.collect()
        torch.cuda.empty_cache()

        rows.append(evaluate(
            label,
            "COCO then local fine-tuning",
            checkpoint,
            folder,
            expected_names,
        ))
        write_results(folder, rows)

    ranked = sorted(
        rows,
        key=lambda row: row["map50_95_percent"],
        reverse=True,
    )
    write_results(folder, ranked)

    print("\nVALIDATION COMPARISON FINISHED")

    for row in ranked:
        print(
            f"\n{row['model']}\n"
            f"  Precision: {row['precision_percent']:.2f}%\n"
            f"  Recall: {row['recall_percent']:.2f}%\n"
            f"  mAP50: {row['map50_percent']:.2f}%\n"
            f"  mAP50-95: {row['map50_95_percent']:.2f}%"
        )

    print(
        "\nHighest validation mAP50-95:",
        ranked[0]["model"],
    )
    print("Results:", folder / "comparison.csv")
    print("The website checkpoint was not replaced.")


if __name__ == "__main__":
    freeze_support()
    main()
