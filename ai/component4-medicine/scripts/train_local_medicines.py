"""Fine-tune the MEDISEG checkpoint on the local medicine dataset."""

from multiprocessing import freeze_support
from pathlib import Path

import torch
from ultralytics import YOLO


COMPONENT = Path(__file__).resolve().parents[1]
CHECKPOINT = COMPONENT / "models" / "mediseg_best.pt"
DATA = COMPONENT / "data" / "local_medicines_yolo" / "data.yaml"
RUNS = COMPONENT / "runs" / "local_medicines"


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is not available in this environment.")

    if not CHECKPOINT.is_file():
        raise FileNotFoundError(f"Checkpoint missing: {CHECKPOINT}")

    if not DATA.is_file():
        raise FileNotFoundError(f"Dataset configuration missing: {DATA}")

    print("GPU:", torch.cuda.get_device_name(0))
    print("Starting checkpoint:", CHECKPOINT)
    print("Dataset:", DATA)
    print("Original checkpoint will remain unchanged.")

    model = YOLO(str(CHECKPOINT))

    if model.task != "detect":
        raise RuntimeError("Expected an object detection checkpoint.")

    model.train(
        data=str(DATA),
        epochs=100,
        patience=20,
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        amp=True,
        cache=False,
        optimizer="AdamW",
        lr0=0.001,
        seed=42,
        deterministic=True,
        project=str(RUNS),
        name="mediseg_finetune",
        exist_ok=False,
        save=True,
        plots=True,
        close_mosaic=10,
    )

    run_dir = Path(model.trainer.save_dir)
    best_path = run_dir / "weights" / "best.pt"

    print("\nTRAINING FINISHED")
    print("Results folder:", run_dir)
    print("Best checkpoint:", best_path)

    # Validate the selected checkpoint on validation data.
    # Keep test data untouched until model selection is finished.
    best_model = YOLO(str(best_path))
    metrics = best_model.val(
        data=str(DATA),
        split="val",
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        project=str(RUNS),
        name=run_dir.name + "_validation",
        plots=True,
    )

    print("\nVALIDATION METRICS")
    print("Precision:", float(metrics.box.mp))
    print("Recall:", float(metrics.box.mr))
    print("mAP50:", float(metrics.box.map50))
    print("mAP50-95:", float(metrics.box.map))


if __name__ == "__main__":
    freeze_support()
    main()