"""Reviewed prescription storage and model-label/count comparison."""
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# This is a model-score threshold, not a calibrated correctness probability.
MIN_CONFIDENCE = 0.65


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


def save_prescription(database, payload, products):
    if payload.get("reviewed") is not True:
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
            raise ValueError("A selected product is not supported by the current model.")
        if product_id and product_id in product_ids:
            raise ValueError("Combine duplicate product rows into one tray quantity.")
        if product_id:
            product_ids.add(product_id)
        quantity = item.get("quantity")
        if type(quantity) is not int or not 1 <= quantity <= 100:
            raise ValueError("Tray quantity must be a whole number between 1 and 100.")
        cleaned.append({
            "medicineName": clean_text(item.get("medicineName"), "medicine name", True),
            "strength": clean_text(item.get("strength", ""), "strength", limit=80),
            "productId": product_id,
            "productName": products[product_id]["name"] if product_id else None,
            "quantity": quantity,
        })
    record = {
        "id": "rx-" + uuid4().hex,
        "createdAt": now(),
        "reference": clean_text(payload.get("reference", ""), "tray reference"),
        "doseLabel": clean_text(payload.get("doseLabel", ""), "dose or tray label", True),
        "items": cleaned,
        "status": "reviewed-draft",
        "reviewed": True,
        "comparisonReady": all(item["productId"] for item in cleaned),
        "scope": "MEDISEG Hong Kong products",
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


def build_comparison(prescription, detections, products):
    if not prescription.get("reviewed") or not prescription.get("items"):
        raise ValueError("A reviewed prescription is required.")
    unsupported = [
        item["medicineName"] for item in prescription["items"]
        if not item["productId"] or item["productId"] not in products
    ]
    if unsupported:
        raise ValueError("Unsupported prescription medicines: " + ", ".join(unsupported))
    if not isinstance(detections, list):
        raise ValueError("Invalid model detections.")
    found = Counter()
    uncertain = []
    for detection in detections:
        if not isinstance(detection, dict):
            raise ValueError("Invalid model detection.")
        label = detection.get("label")
        confidence = detection.get("confidence")
        box = detection.get("bbox")
        if (
            not isinstance(label, str)
            or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or not 0 <= confidence <= 1
            or not isinstance(box, list) or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
        ):
            raise ValueError("Invalid model detection fields.")
        if label not in products or detection.get("unmapped") or confidence < MIN_CONFIDENCE:
            uncertain.append({
                **detection,
                "reason": "Unsupported class" if label not in products or detection.get("unmapped")
                else "Low model confidence",
            })
        else:
            found[label] += 1
    expected = {item["productId"]: item["quantity"] for item in prescription["items"]}
    medicine_rows = {item["productId"]: item for item in prescription["items"]}
    rows = []
    for product_id in sorted(set(expected) | set(found)):
        item = medicine_rows.get(product_id, {})
        rows.append({
            "productId": product_id,
            "medicineName": item.get("medicineName", products[product_id]["name"]),
            "strength": item.get("strength", ""),
            "expected": expected.get(product_id, 0),
            "found": found.get(product_id, 0),
            "difference": found.get(product_id, 0) - expected.get(product_id, 0),
        })
    mismatch = any(row["difference"] != 0 for row in rows)
    status = (
        "Inconclusive — review required" if uncertain
        else "Count differences — review required" if mismatch
        else "Counts match — review required"
    )
    return {
        "id": "comparison-" + uuid4().hex,
        "mode": "live",
        "createdAt": now(),
        "reference": prescription.get("reference", ""),
        "prescription": prescription,
        "status": status,
        "rows": rows,
        "uncertain": uncertain,
        "confidenceThreshold": MIN_CONFIDENCE,
        "requiresManualReview": True,
        "comparisonPerformed": True,
        "clinicalComplianceConfirmed": False,
        "scope": "MEDISEG Hong Kong product labels and tray quantities",
        "notes": (
            "Compares model product labels and counted detections with the reviewed tray list. "
            "Uncertain detections are excluded from counts. Strength, dose timing, "
            "administration route and clinical suitability are not verified. "
            "Matching counts do not confirm that the actual medicines are correct."
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
            "SELECT payload FROM comparisons ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(row[0]) for row in rows]
