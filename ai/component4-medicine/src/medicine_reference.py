"""Experimental appearance rules for five user-declared medicine samples.

No medical identity inference, calibrated confidence, or physical-size measurement.
This profile assumes the declared products, a near-overhead view, and one plane.
"""
import os
import numpy as np

PROFILE = "declared-five-samples-v1"
LABELS = {
    "pink": "Verapamil 40mg",
    "orange-small": "Nitedipine -Nicardia E 20mg",
    "orange-large": "Atenolol 50mg",
    "white-small": "Amlodipine 2.5mg",
    "white-large": "Irbesartan_Irovel_150mg",
}


def appearance(image, box):
    x1, y1, x2, y2 = box
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(image.width, int(x2)), min(image.height, int(y2))
    w, h = x2 - x1, y2 - y1
    if min(w, h) < 12 or not 0.65 <= w / h <= 1.55:
        return "unknown", 0.0
    with image.crop((x1, y1, x2, y2)) as crop:
        with crop.resize((80, 80)) as resized:
            with resized.convert("HSV") as hsv_image:
                hsv = np.array(hsv_image, dtype=float)
    yy, xx = np.ogrid[:80, :80]
    mask = ((xx - 39.5) / 23) ** 2 + ((yy - 39.5) / 23) ** 2 <= 1
    hue, sat, val = hsv[:, :, 0] * 360 / 255, hsv[:, :, 1] / 255, hsv[:, :, 2] / 255
    visible = mask & (val >= 0.20)
    if visible.sum() < mask.sum() * 0.75:
        return "unknown", w * h
    colours = {
        "pink": (hue >= 300) & (hue <= 355) & (sat >= 0.40),
        "orange": (hue >= 5) & (hue <= 55) & (sat >= 0.40),
        "white": (sat <= 0.28) & (val >= 0.35),
    }
    fractions = {name: float((visible & test).sum()) / visible.sum() for name, test in colours.items()}
    name = max(fractions, key=fractions.get)
    return (name if fractions[name] >= 0.65 else "unknown"), float(w * h)


def apply_reference_profile(image, detections, class_names):
    if os.environ.get("RX_REFERENCE_MODE", "off").strip().lower() != "five-pill-reference":
        return detections
    groups = {"pink": [], "orange": [], "white": [], "unknown": []}
    output = []
    for detection in detections:
        colour, area = appearance(image, detection["bbox"])
        row = dict(detection)
        row.update({
            "rawModelResult": dict(detection),
            "rawModelConfidence": detection["confidence"],
            "labelSource": "reference-unresolved",
            "referenceMode": True,
            "referenceProfile": PROFILE,
            "referenceAssigned": False,
            "referenceAppearance": colour,
            "referenceBoxArea": area,
            "requiresManualReview": True,
            "identityUncertain": True,
            "unmapped": True,
            "classId": -1,
            "label": "__uncertain__",
            "alternatives": [],
        })
        groups[colour].append(len(output))
        output.append(row)
    assignments = {}
    reason = "Reference profile requires five separated boxes: one pink, two orange and two white."
    valid = len(output) == 5 and all(len(groups[k]) == n for k, n in (("pink", 1), ("orange", 2), ("white", 2), ("unknown", 0)))
    if valid:
        assignments[groups["pink"][0]] = LABELS["pink"]
        for colour in ("orange", "white"):
            small, large = sorted(groups[colour], key=lambda i: output[i]["referenceBoxArea"])
            ratio = output[large]["referenceBoxArea"] / max(output[small]["referenceBoxArea"], 1)
            if not 1.30 <= ratio <= 3.50:
                valid = False
                reason = "Relative sizes are too similar or outside this reference profile."
                break
            assignments[small] = LABELS[colour + "-small"]
            assignments[large] = LABELS[colour + "-large"]
    if valid and not all(label in class_names for label in assignments.values()):
        valid = False
        reason = "Reference sample label is missing from the active model catalog."
    if not valid:
        return detections

    for index, row in enumerate(output):
        if valid:
            label = assignments[index]
            row.update({"label": label, "classId": list(class_names).index(label),
                        "labelSource": "reference-rule", "referenceAssigned": True,
                        "identityUncertain": False, "unmapped": False,
                        "selectionPolicy": "declared-samples-colour-relative-area",
                        "reason": "Reference-based sample label; NOT a model identity prediction. Review packaging."})
        else:
            row["reason"] = reason
    return output
