"""Reviewed prescriptions and explicitly scoped tray comparisons."""

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


MIN_CONFIDENCE = 0.60


def reference_assigned(detection):
    return (
        detection.get("referenceMode") is True
        and detection.get("referenceAssigned") is True
        and detection.get("labelSource") == "reference-rule"
        and detection.get("referenceProfile") == "declared-five-samples-v1"
        and not detection.get("identityUncertain")
    )

def now():
    return datetime.now(timezone.utc).isoformat()


def connect(database):
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database), timeout=10)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS reviewed_prescriptions "
        "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS comparisons "
        "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    return connection


def clean_text(value, field, required=False, limit=200):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"Invalid {field}.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Enter {field}.")
    return value


def validate_prescription(prescription):
    if not isinstance(prescription, dict):
        raise ValueError("A reviewed prescription is required.")

    items = prescription.get("items")
    if (
        prescription.get("reviewed") is not True
        or not isinstance(items, list)
        or not 1 <= len(items) <= 50
    ):
        raise ValueError("A reviewed prescription is required.")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid prescription row.")
        clean_text(item.get("medicineName"), "medicine name", True)
        quantity = item.get("quantity")
        if type(quantity) is not int or not 1 <= quantity <= 100:
            raise ValueError("Tray quantity must be an integer from 1 to 100.")

    return items


def validate_detections(detections):
    if not isinstance(detections, list):
        raise ValueError("Invalid model detections.")

    for detection in detections:
        if not isinstance(detection, dict):
            raise ValueError("Invalid model detection.")

        confidence = detection.get("confidence")
        box = detection.get("bbox")

        if (
            not isinstance(detection.get("label"), str)
            or type(confidence) not in (int, float)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
            or not isinstance(box, list)
            or len(box) != 4
            or any(
                type(value) not in (int, float)
                or not math.isfinite(value)
                for value in box
            )
        ):
            raise ValueError("Invalid model detection fields.")

        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError("Invalid detection box.")

    return detections


def save_prescription(database, payload, products):
    if not isinstance(payload, dict) or payload.get("reviewed") is not True:
        raise ValueError("Review the prescription before saving.")

    items = payload.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        raise ValueError("Add between 1 and 50 medicine rows.")

    cleaned = []
    product_ids = set()

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid medicine row.")

        product_id = clean_text(item.get("productId", ""), "product ID")

        if product_id and product_id not in products:
            raise ValueError(
                "A selected product is not supported by the current model."
            )

        if product_id and product_id in product_ids:
            raise ValueError(
                "Combine duplicate product rows into one tray quantity."
            )

        if product_id:
            product_ids.add(product_id)

        quantity = item.get("quantity")
        if type(quantity) is not int or not 1 <= quantity <= 100:
            raise ValueError(
                "Tray quantity must be a whole number between 1 and 100."
            )

        cleaned.append({
            "medicineName": clean_text(
                item.get("medicineName"), "medicine name", True
            ),
            "strength": clean_text(
                item.get("strength", ""), "strength", limit=80
            ),
            "productId": product_id,
            "productName": products[product_id]["name"] if product_id else None,
            "quantity": quantity,
        })

    record = {
        "id": "rx-" + uuid4().hex,
        "createdAt": now(),
        "reference": clean_text(payload.get("reference", ""), "tray reference"),
        "doseLabel": clean_text(
            payload.get("doseLabel", ""), "dose or tray label", True
        ),
        "items": cleaned,
        "status": "reviewed-draft",
        "reviewed": True,
        "comparisonReady": all(item["productId"] for item in cleaned),
        "totalCountReady": True,
        "scope": "User-reviewed tray list",
        "source": "user-reviewed",
        "doctorApproved": False,
    }

    connection = connect(database)
    try:
        with connection:
            connection.execute(
                "INSERT INTO reviewed_prescriptions VALUES (?, ?, ?)",
                (record["id"], record["createdAt"], json.dumps(record)),
            )
    finally:
        connection.close()

    return record


def get_prescription(database, prescription_id):
    connection = connect(database)
    try:
        row = connection.execute(
            "SELECT payload FROM reviewed_prescriptions WHERE id = ?",
            (prescription_id,),
        ).fetchone()
    finally:
        connection.close()

    return json.loads(row[0]) if row else None


def base_result(prescription, comparison_type):
    return {
        "id": "comparison-" + uuid4().hex,
        "mode": "live",
        "createdAt": now(),
        "reference": prescription.get("reference", ""),
        "prescription": prescription,
        "comparisonType": comparison_type,
        "confidenceThreshold": MIN_CONFIDENCE,
        "requiresManualReview": True,
        "comparisonPerformed": True,
        "clinicalComplianceConfirmed": False,
    }


def build_comparison(prescription, detections, products):
    items = validate_prescription(prescription)

    unsupported = [
        item["medicineName"]
        for item in items
        if not item.get("productId") or item["productId"] not in products
    ]

    if unsupported:
        raise ValueError(
            "Unsupported prescription medicines: " + ", ".join(unsupported)
        )

    product_ids = [item["productId"] for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValueError("Combine duplicate product rows before comparing.")

    validate_detections(detections)
    found = Counter()
    uncertain = []

    for detection in detections:
        label = detection["label"]
        unsupported_class = (
            label not in products or bool(detection.get("unmapped"))
        )

        if (unsupported_class or detection.get("identityUncertain")
            or (detection["confidence"] < MIN_CONFIDENCE and not reference_assigned(detection))):
            uncertain.append({
                **detection,
                "reason": (
                    "Unsupported class"
                    if unsupported_class
                    else "Low model confidence"
                ),
            })
        else:
            found[label] += 1

    expected = {item["productId"]: item["quantity"] for item in items}
    medicine_rows = {item["productId"]: item for item in items}
    rows = []

    for product_id in sorted(set(expected) | set(found)):
        item = medicine_rows.get(product_id, {})
        rows.append({
            "productId": product_id,
            "medicineName": item.get(
                "medicineName", products[product_id]["name"]
            ),
            "strength": item.get("strength", ""),
            "expected": expected.get(product_id, 0),
            "found": found.get(product_id, 0),
            "difference": (
                found.get(product_id, 0) - expected.get(product_id, 0)
            ),
        })

    uses_reference = any(d.get("referenceMode") for d in detections)
    mismatch = any(row["difference"] != 0 for row in rows)
    status = (
        "Inconclusive — review required"
        if uncertain
        else "Count differences — review required"
        if mismatch
        else "Counts match — review required"
    )

    if uses_reference:
        status = (
            "Reference comparison inconclusive — review required" if uncertain
            else "Reference count differences — review required" if mismatch
            else "Reference counts match — identities NOT verified"
        )

    return {
        **base_result(prescription, "product-count"),
        "usesReferenceLabels": uses_reference,
        "labelSource": "reference-assisted" if uses_reference else "model",
        "referenceAssignedCount": sum(reference_assigned(d) for d in detections),
        "status": status,
        "rows": rows,
        "uncertain": uncertain,
        "identitiesConfirmed": False,
        "scope": "Predicted product labels and tray quantities",
        "notes": (
            "Experimental reference comparison for the user's declared five samples. "
            "Assigned labels use colour and relative box area, not confirmed medicine identities. "
            "Model confidence thresholds do not validate reference labels. "
            "Review the original prescription and packaging. Matching reference counts do not "
            "confirm strength, timing, route or clinical suitability."
            if uses_reference else
            "Compares predicted product labels and counted detections with "
            "the reviewed tray list. Uncertain detections are excluded. "
            "Strength, timing, route and clinical suitability are not verified. "
            "Matching counts do not confirm the actual medicine identities."
        ),
    }


def build_total_count_comparison(prescription, detections):
    items = validate_prescription(prescription)
    validate_detections(detections)

    expected_total = sum(item["quantity"] for item in items)
    detected_total = len(detections)
    difference = detected_total - expected_total

    low_confidence_count = sum(
        detection["confidence"] < MIN_CONFIDENCE
        for detection in detections
    )

    status = (
        "Total count inconclusive — review required"
        if low_confidence_count
        else "Total counts equal — identities not checked"
        if difference == 0
        else "Total counts differ — identities not checked"
    )

    return {
        **base_result(prescription, "total-count"),
        "status": status,
        "expectedTotal": expected_total,
        "detectedTotal": detected_total,
        "difference": difference,
        "lowConfidenceCount": low_confidence_count,
        "identitiesChecked": False,
        "scope": "Total detected objects only",
        "notes": (
            "Counts all returned detection boxes, including low-confidence "
            "and unsupported-class detections. The detector can miss pills "
            "or detect other objects. Medicine identities, quantities per "
            "medicine, strength and timing are not checked. Equal totals "
            "do not confirm that the prepared medicines are correct."
        ),
    }


def save_comparison(database, result):
    connection = connect(database)
    try:
        with connection:
            connection.execute(
                "INSERT INTO comparisons VALUES (?, ?, ?)",
                (result["id"], result["createdAt"], json.dumps(result)),
            )
    finally:
        connection.close()


def list_history(database):
    connection = connect(database)
    try:
        rows = connection.execute(
            "SELECT payload FROM comparisons "
            "ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    finally:
        connection.close()

    return [json.loads(row[0]) for row in rows]