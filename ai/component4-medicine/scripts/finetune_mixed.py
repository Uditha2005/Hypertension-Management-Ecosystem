from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path
import json

import torch
import yaml
from ultralytics import YOLO


def main():
    component = Path(__file__).resolve().parents[1]

    checkpoint = component / "models/local_medicines_best.pt"
    dataset = component / "data/local_medicines_yolo_v2/data.yaml"

    if not checkpoint.is_file():
        raise SystemExit(f"Checkpoint missing: {checkpoint}")

    if not dataset.is_file():
        raise SystemExit(f"Dataset missing: {dataset}")

    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable. Use the .venv-train environment.")

    config = yaml.safe_load(dataset.read_text(encoding="utf-8-sig"))
    raw_names = config["names"]
    names = (
        [raw_names[index] for index in range(len(raw_names))]
        if isinstance(raw_names, dict)
        else list(raw_names)
    )

    model = YOLO(str(checkpoint))
    model_names = (
        [model.names[index] for index in range(len(model.names))]
        if isinstance(model.names, dict)
        else list(model.names)
    )

    if names != model_names:
        raise SystemExit("Dataset class order does not match the checkpoint.")

    run_name = "mixed_finetune_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    print("GPU:", torch.cuda.get_device_name(0))
    print("Starting from:", checkpoint)
    print("Dataset:", dataset)

    model.train(
        data=str(dataset),
        epochs=30,
        patience=10,
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        amp=True,
        cache=False,
        optimizer="AdamW",
        lr0=0.0001,
        seed=42,
        deterministic=True,
        project=str(component / "runs/local_medicines"),
        name=run_name,
        exist_ok=False,
        save=True,
        plots=True,
        close_mosaic=5,
    )

    run_dir = Path(model.trainer.save_dir).resolve()
    best = run_dir / "weights/best.pt"

    if not best.is_file():
        raise SystemExit("Training ended without a best.pt checkpoint.")

    record = {
        "bestCheckpoint": str(best),
        "runDirectory": str(run_dir),
        "dataset": str(dataset),
        "startingCheckpoint": str(checkpoint),
        "note": (
            "The tray2 photo is included in training. "
            "Performance on that photo is not independent test evidence."
        ),
    }

    record_path = component / "runs/local_medicines/latest_mixed_training.json"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print("\nTRAINING FINISHED")
    print("Best checkpoint:", best)
    print("Record:", record_path)
    print("Website checkpoint has not been replaced yet.")


if __name__ == "__main__":
    freeze_support()
    main()
