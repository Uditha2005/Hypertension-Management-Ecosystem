"""Local medicine detection using two inference resolutions.

Conflicting predictions remain unidentified.
Model scores are never increased to pass comparison thresholds.
"""

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from ultralytics import YOLO


COMPONENT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = COMPONENT_DIR / "models" / "local_medicines_best.pt"

MODEL_SCOPE = "Locally collected medicine dataset — 22 classes"
MODEL_ID = "local-medicines-mixed22-multiscale-v1"

INFERENCE_SIZES = (640, 1280)
MERGE_IOU = 0.55
UNCERTAIN_LABEL = "__uncertain__"

PREDICTION_LOCK = Lock()

# IDs 0–19 remain unchanged. New classes are appended.
EXPECTED_CLASSES = (
    "Amlodipine 2.5mg",
    "Angiopril 25mg",
    "Atenolol 50mg",
    "Brisopol 5mg",
    "Carvedilil -3-125mg",
    "Clopidogrel -clopact- 75mg",
    "Ecosprine -asprin- 75mg",
    "Enalapril 5mg",
    "Ezitimibe -ezita- 10mg",
    "Indapamide 1.5mg",
    "Irbesartan_Irovel_150mg",
    "Losartan 25mg",
    "Losartan 50mg",
    "Metaprolol -Betaloc- 50mg",
    "Nitedipine -Nicardia E 20mg",
    "Ramipril 5mg",
    "Spironolactone 25mg",
    "Telmisartan (Telday)",
    "Telmisartan (Telsart)",
    "Verapamil 40mg",
    "Amlodipine 5mg",
    "Diltiazem 90mg",
)


def class_names(model):
    names = model.names
    if isinstance(names, dict):
        return [str(names[index]) for index in range(len(names))]
    return [str(name) for name in names]


@lru_cache(maxsize=1)
def load_model():
    """Load and validate the deployed checkpoint once per API process."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Local model not found: {MODEL_PATH}")

    model = YOLO(str(MODEL_PATH))

    if model.task != "detect":
        raise ValueError("Expected an object detection checkpoint.")

    if class_names(model) != list(EXPECTED_CLASSES):
        raise ValueError(
            "Checkpoint classes/order do not match the 22-class catalog. "
            "Install the completed mixed_22 best.pt and restart the API."
        )

    return model


def box_iou(first, second):
    """Intersection over union in original-image coordinates."""
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])

    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (
        max(0.0, first[2] - first[0])
        * max(0.0, first[3] - first[1])
    )
    second_area = (
        max(0.0, second[2] - second[0])
        * max(0.0, second[3] - second[1])
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def collect_candidates(result, image_size):
    candidates = []
    if result.boxes is None:
        return candidates

    boxes = result.boxes.xyxy.cpu().tolist()
    scores = result.boxes.conf.cpu().tolist()
    classes = result.boxes.cls.cpu().tolist()

    for coordinates, score, class_id in zip(boxes, scores, classes):
        class_id = int(class_id)
        candidates.append({
            "classId": class_id,
            "label": str(result.names[class_id]),
            "confidence": float(score),
            "bbox": [float(value) for value in coordinates],
            "imageSize": image_size,
        })

    return candidates


def merge_candidates(candidates):
    """Conservatively group overlapping predictions.

    Every member must overlap every other member in its group.
    Different class labels remain unresolved.
    """
    groups = []
    ordered = sorted(
        candidates,
        key=lambda item: item["confidence"],
        reverse=True,
    )

    for candidate in ordered:
        matching_groups = [
            index
            for index, group in enumerate(groups)
            if all(
                box_iou(candidate["bbox"], member["bbox"]) >= MERGE_IOU
                for member in group
            )
        ]

        if len(matching_groups) == 1:
            groups[matching_groups[0]].append(candidate)
        else:
            groups.append([candidate])

    detections = []

    for group in groups:
        strongest = max(group, key=lambda item: item["confidence"])
        labels = {item["label"] for item in group}
        sizes = [item["imageSize"] for item in group]

        ambiguous_geometry = len(sizes) != len(set(sizes))
        conflicting_labels = len(labels) > 1
        uncertain = conflicting_labels or ambiguous_geometry

        alternatives = [
            {
                "classId": item["classId"],
                "label": item["label"],
                "confidence": round(item["confidence"], 4),
                "imageSize": item["imageSize"],
                "bbox": [round(value, 2) for value in item["bbox"]],
            }
            for item in group
        ]

        if conflicting_labels:
            reason = "Different class labels across inference resolutions."
        elif ambiguous_geometry:
            reason = "Overlapping boxes may represent more than one object."
        elif len(set(sizes)) == 1:
            reason = "Detected at one inference resolution only."
        else:
            reason = "Same class label at both inference resolutions."

        detections.append({
            "classId": -1 if uncertain else strongest["classId"],
            "label": UNCERTAIN_LABEL if uncertain else strongest["label"],
            "confidence": round(strongest["confidence"], 4),
            "bbox": [round(value, 2) for value in strongest["bbox"]],
            "unmapped": uncertain,
            "identityUncertain": uncertain,
            "resolutionAgreement": (
                not uncertain
                and len(set(sizes)) == len(INFERENCE_SIZES)
            ),
            "inferenceSizes": sorted(set(sizes)),
            "alternatives": alternatives,
            "reason": reason,
            "modelId": MODEL_ID,
            "requiresManualReview": True,
        })

    detections.sort(
        key=lambda item: (item["bbox"][1], item["bbox"][0])
    )
    return detections


def annotation_font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


class MergedPrediction:
    """Provide plot() and save() used by the API and CLI.

    Box colours show prediction state, not prescription agreement.
    plot() returns BGR, matching main.py.
    """

    def __init__(self, rgb_image, detections):
        self.image = rgb_image.copy()
        self.detections = detections

    def annotated_image(self):
        annotated = self.image.copy()
        draw = ImageDraw.Draw(annotated)
        font_size = max(14, min(30, round(annotated.width / 45)))
        font = annotation_font(font_size)
        line_width = max(2, round(annotated.width / 350))

        for index, detection in enumerate(self.detections, start=1):
            left, top, right, bottom = detection["bbox"]

            if detection["identityUncertain"]:
                color = "#b67612"
                names = list(dict.fromkeys(
                    item["label"] for item in detection["alternatives"]
                ))
                label = f"{index}. Medicine not identified - review required"
            else:
                # Neutral outline: a prediction is not a confirmed match.
                color = "#4b6260"
                label = (
                    f"{index}. {detection['label']} "
                    f"{detection['confidence']:.2f}"
                )

            draw.rectangle(
                (left, top, right, bottom),
                outline=color,
                width=line_width,
            )

            bounds = draw.textbbox((0, 0), label, font=font)
            text_width = bounds[2] - bounds[0]
            text_height = bounds[3] - bounds[1]
            x = max(
                0,
                min(int(left), annotated.width - text_width - 8),
            )
            y = max(0, int(top) - text_height - 10)

            draw.rectangle(
                (x, y, x + text_width + 8, y + text_height + 8),
                fill=color,
            )
            draw.text(
                (x + 4, y + 4 - bounds[1]),
                label,
                fill="white",
                font=font,
            )

        return annotated

    def plot(self):
        with self.annotated_image() as annotated:
            rgb = np.array(annotated)
        return rgb[:, :, ::-1].copy()

    def save(self, filename):
        with self.annotated_image() as annotated:
            annotated.save(str(filename))


def detect_pills(image, confidence=0.25):
    """Run both resolutions and return merged predictions."""
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 < confidence <= 1
    ):
        raise ValueError("Confidence must be between 0 and 1.")

    prepared = ImageOps.exif_transpose(image).convert("RGB")

    try:
        candidates = []

        with PREDICTION_LOCK:
            model = load_model()

            for size in INFERENCE_SIZES:
                result = model.predict(
                    source=prepared,
                    imgsz=size,
                    conf=float(confidence),
                    iou=0.7,
                    device="cpu",
                    agnostic_nms=True,
                    verbose=False,
                )[0]
                candidates.extend(collect_candidates(result, size))

        detections = merge_candidates(candidates)
        prediction = MergedPrediction(prepared, detections)
        return detections, prediction
    finally:
        prepared.close()


def main():
    parser = argparse.ArgumentParser(
        description="22-class local medicine detection at 640 and 1280."
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Original tray photo path.",
    )
    parser.add_argument("--confidence", type=float, default=0.25)
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Photo not found: {args.image}")

    if not math.isfinite(args.confidence) or not 0 < args.confidence <= 1:
        parser.error("Confidence must be between 0 and 1.")

    with Image.open(args.image) as image:
        detections, prediction = detect_pills(image, args.confidence)

    output = COMPONENT_DIR / "outputs" / "multiscale"
    output.mkdir(parents=True, exist_ok=True)
    annotated_path = output / f"{args.image.stem}_detected.jpg"
    json_path = output / f"{args.image.stem}_detections.json"

    prediction.save(annotated_path)

    payload = {
        "model": MODEL_PATH.name,
        "modelId": MODEL_ID,
        "scope": MODEL_SCOPE,
        "inferenceSizes": list(INFERENCE_SIZES),
        "count": len(detections),
        "detections": detections,
        "requiresManualReview": True,
    }

    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("\nAnnotated photo:", annotated_path)
    print("Prediction data:", json_path)


if __name__ == "__main__":
    main()