import argparse
import json
from functools import lru_cache
from pathlib import Path
from threading import Lock

from PIL import Image, ImageOps
from ultralytics import YOLO


COMPONENT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = COMPONENT_DIR / "models" / "mediseg_best.pt"
PREDICTION_LOCK = Lock()


@lru_cache(maxsize=1)
def load_model():
    """Load the trained model once."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Model file not found: {MODEL_PATH}"
        )

    return YOLO(str(MODEL_PATH))


def detect_pills(image, confidence=0.25):
    """
    Return model predictions and the annotated image result.

    Confidence is a detection filter, not a medicine safety guarantee.
    Predictions refer to the MEDISEG Hong Kong product classes.
    """
    if not 0 < confidence <= 1:
        raise ValueError("Confidence must be between 0 and 1.")

    image = ImageOps.exif_transpose(image).convert("RGB")

    with PREDICTION_LOCK:
        model = load_model()

        result = model.predict(
            source=image,
            imgsz=640,
            conf=confidence,
            device="cpu",
            agnostic_nms=True,
            verbose=False,
        )[0]

    detections = []

    if result.boxes is not None:
        boxes = result.boxes.xyxy.cpu().tolist()
        scores = result.boxes.conf.cpu().tolist()
        classes = result.boxes.cls.cpu().tolist()

        for coordinates, score, class_id in zip(
            boxes, scores, classes
        ):
            class_id = int(class_id)
            label = result.names[class_id]

            detections.append({
                "classId": class_id,
                "label": label,
                "confidence": round(float(score), 4),
                "bbox": [
                    round(float(value), 2)
                    for value in coordinates
                ],
                "unmapped": label == "pills",
            })

    return detections, result


def main():
    parser = argparse.ArgumentParser(
        description="Detect pills in a photo."
    )

    parser.add_argument(
        "image",
        type=Path,
        help="Path to the tray photo.",
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="Detection confidence filter. Default: 0.25.",
    )

    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Image not found: {args.image}")

    if not 0 < args.confidence <= 1:
        parser.error("Confidence must be between 0 and 1.")

    with Image.open(args.image) as image:
        detections, result = detect_pills(
            image,
            confidence=args.confidence,
        )

    output_dir = COMPONENT_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    annotated_path = (
        output_dir / f"{args.image.stem}_detected.jpg"
    )

    json_path = (
        output_dir / f"{args.image.stem}_detections.json"
    )

    result.save(filename=str(annotated_path))

    payload = {
        "model": MODEL_PATH.name,
        "scope": "MEDISEG Hong Kong product classes",
        "count": len(detections),
        "detections": detections,
    }

    json_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(payload, indent=2))
    print(f"\nAnnotated photo: {annotated_path}")
    print(f"Prediction data: {json_path}")


if __name__ == "__main__":
    main()