"""Detect local medicines with one selected prediction per overlapping object.

The highest-scoring prediction is selected across inference resolutions.
Scores below 0.60 remain unidentified. Scores are not correctness guarantees.
"""

from medicine_reference import apply_reference_profile

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
MODEL_ID = "local-medicines-mixed22-colour-check-v3"

INFERENCE_SIZES = (640, 1280)
MERGE_IOU = 0.55
IDENTITY_THRESHOLD = 0.60
UNCERTAIN_LABEL = "__uncertain__"

PREDICTION_LOCK = Lock()

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
    """Load the deployed checkpoint once per API process."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Local model not found: {MODEL_PATH}")

    model = YOLO(str(MODEL_PATH))

    if model.task != "detect":
        raise ValueError("Expected an object detection checkpoint.")

    if class_names(model) != list(EXPECTED_CLASSES):
        raise ValueError(
            "Checkpoint class names/order do not match the "
            "22-class local catalog."
        )

    return model


def box_iou(first, second):
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
    if result.boxes is None:
        return []

    boxes = result.boxes.xyxy.cpu().tolist()
    scores = result.boxes.conf.cpu().tolist()
    classes = result.boxes.cls.cpu().tolist()

    candidates = []

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



def pill_colour(image, bbox):
    """Estimate colour from the central region, excluding most background.

    This is a heuristic, not pill segmentation or identity verification.
    """
    left, top, right, bottom = bbox
    width, height = image.size

    left = max(0, min(width, int(left)))
    top = max(0, min(height, int(top)))
    right = max(0, min(width, int(math.ceil(right))))
    bottom = max(0, min(height, int(math.ceil(bottom))))

    if right - left < 8 or bottom - top < 8:
        return "unknown"

    with image.crop((left, top, right, bottom)) as crop:
        with crop.resize((80, 80)) as resized:
            with resized.convert("HSV") as hsv_image:
                hsv = np.asarray(hsv_image, dtype=np.float32)

    yy, xx = np.ogrid[:80, :80]
    centre = (
        ((xx - 39.5) / 25.0) ** 2
        + ((yy - 39.5) / 25.0) ** 2
    ) <= 1.0

    hue = hsv[:, :, 0] * (360.0 / 255.0)
    saturation = hsv[:, :, 1] / 255.0
    brightness = hsv[:, :, 2] / 255.0

    usable = centre & (brightness >= 0.15)
    count = int(usable.sum())

    if count < 100:
        return "unknown"

    pink = (
        usable
        & (hue >= 300)
        & (hue <= 355)
        & (saturation >= 0.40)
        & (brightness >= 0.25)
    )

    brown = (
        usable
        & (hue >= 5)
        & (hue <= 40)
        & (saturation >= 0.35)
        & (brightness >= 0.20)
        & (brightness <= 0.90)
    )

    if float(pink.sum()) / count >= 0.65:
        return "pink"

    if float(brown.sum()) / count >= 0.65:
        return "brown"

    return "unknown"


def merge_candidates(candidates, image=None):
    """Select one label per overlapping object, with a limited colour check."""
    threshold = 0.60
    verapamil = "Verapamil 40mg"
    clopidogrel = "Clopidogrel -clopact- 75mg"

    groups = []

    for candidate in sorted(
        candidates,
        key=lambda item: item["confidence"],
        reverse=True,
    ):
        matches = [
            (box_iou(candidate["bbox"], group[0]["bbox"]), index)
            for index, group in enumerate(groups)
        ]

        overlap, index = max(matches) if matches else (0.0, -1)

        if overlap >= MERGE_IOU:
            groups[index].append(candidate)
        else:
            groups.append([candidate])

    detections = []

    for group in groups:
        strongest = group[0]
        selected = strongest
        colour = (
            pill_colour(image, strongest["bbox"])
            if image is not None
            else "unknown"
        )

        rejected = False
        selection = "highest-model-score"
        colour_note = ""

        # Apply this rule only to the confirmed reference pair.
        if strongest["label"] == clopidogrel and colour == "pink":
            matching = [
                item for item in group
                if item["label"] == verapamil
                and item["confidence"] >= threshold
            ]

            if matching:
                selected = max(
                    matching,
                    key=lambda item: item["confidence"],
                )
                selection = "model-candidate-and-colour"
                colour_note = (
                    "Pink appearance supports an existing Verapamil "
                    "candidate over Clopidogrel; review required."
                )
            else:
                rejected = True
                colour_note = (
                    "Pink appearance conflicts with the Clopidogrel "
                    "reference. No qualifying Verapamil candidate."
                )

        elif strongest["label"] == verapamil and colour == "brown":
            # Do not automatically rename brown pills as Clopidogrel.
            rejected = True
            colour_note = (
                "Brown appearance conflicts with the Verapamil "
                "reference; identity requires review."
            )

        known = selected["label"] in EXPECTED_CLASSES
        identified = (
            known
            and selected["confidence"] >= threshold
            and not rejected
        )

        labels = {item["label"] for item in group}
        sizes = sorted({item["imageSize"] for item in group})

        if colour_note:
            reason = colour_note
        elif not identified:
            reason = "No accepted identity at the 60% threshold."
        elif len(labels) > 1:
            reason = (
                "Highest-scoring label selected despite resolution "
                "disagreement; review required."
            )
        else:
            reason = "Model prediction selected; review required."

        chosen = {
            "classId": selected["classId"],
            "label": selected["label"],
            "confidence": round(selected["confidence"], 4),
            "imageSize": selected["imageSize"],
            "bbox": [round(v, 2) for v in selected["bbox"]],
        }

        detections.append({
            "classId": selected["classId"] if identified else -1,
            "label": selected["label"] if identified else UNCERTAIN_LABEL,
            # Preserve the selected candidate's actual score.
            "confidence": round(selected["confidence"], 4),
            "bbox": [round(v, 2) for v in strongest["bbox"]],
            "unmapped": not identified,
            "identityUncertain": not identified,
            "resolutionAgreement": (
                len(labels) == 1
                and len(sizes) == len(INFERENCE_SIZES)
            ),
            "crossResolutionConflict": len(labels) > 1,
            "inferenceSizes": sizes,
            "alternatives": [chosen] if identified else [],
            "selectionPolicy": selection,
            "identityThreshold": threshold,
            "colourCheck": {
                "appearance": colour,
                "rejected": rejected,
                "note": colour_note,
                "experimental": True,
            },
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
            continue

    return ImageFont.load_default()


class MergedPrediction:
    """API-compatible annotated result; plot() returns BGR."""

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

            if detection.get("referenceMode"):
                color = "#4b6260" if detection.get("referenceAssigned") else "#ad7415"
                label = (
                    f"{index}. {detection['label']}"
                    if detection.get("referenceAssigned")
                    else f"{index}. Unidentified - review"
                )
            elif detection["identityUncertain"]:
                color = "#ad7415"
                label = (
                    f"{index}. Unidentified "
                    f"({detection['confidence']:.0%})"
                )
            else:
                # Outline indicates a prediction, not a verified match.
                color = "#4b6260"
                label = (
                    f"{index}. {detection['label']} "
                    f"{detection['confidence']:.0%}"
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
    """Run both resolutions and select one label per overlapping object."""
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

                candidates.extend(
                    collect_candidates(result, size)
                )

        detections = merge_candidates(candidates, prepared)
        detections = apply_reference_profile(prepared, detections, EXPECTED_CLASSES)
        prediction = MergedPrediction(prepared, detections)

        return detections, prediction

    finally:
        prepared.close()


def main():
    parser = argparse.ArgumentParser(
        description="Local medicine detection with one selected label per pill."
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Original tray photo path.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="Candidate detection filter; identity display requires 0.60.",
    )

    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Photo not found: {args.image}")

    if (
        not math.isfinite(args.confidence)
        or not 0 < args.confidence <= 1
    ):
        parser.error("Confidence must be between 0 and 1.")

    with Image.open(args.image) as image:
        detections, prediction = detect_pills(
            image,
            args.confidence,
        )

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
        "identityThreshold": IDENTITY_THRESHOLD,
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