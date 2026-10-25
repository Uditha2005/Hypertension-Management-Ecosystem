"""Local JSON storage for prototype meal history and optional feedback.

No database connections are used. Files are stored locally for this development
prototype; do not use this storage for shared or production health records.
"""
from __future__ import annotations
import json, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os

RECORD_DIR = Path(os.getenv("COMPONENT3_MEAL_RECORD_DIR", Path(__file__).resolve().parent.parent / "data" / "meal_records"))

def _valid_id(value: str) -> bool:
    return bool(value) and len(value) <= 80 and all(c.isalnum() or c in "-_" for c in value)

def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, OSError):
        return []

def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def save_meal_record(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _valid_id(profile_id):
        raise ValueError("profile_id may contain only letters, digits, hyphen and underscore")
    record = dict(payload)
    record["record_id"] = str(uuid.uuid4())
    record["profile_id"] = profile_id
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    path = RECORD_DIR / f"{profile_id}.json"
    rows = _read(path)
    rows.insert(0, record)
    _write(path, rows[:500])
    return record

def list_meal_records(profile_id: str, limit: int = 30) -> list[dict[str, Any]]:
    if not _valid_id(profile_id):
        raise ValueError("profile_id may contain only letters, digits, hyphen and underscore")
    return _read(RECORD_DIR / f"{profile_id}.json")[:max(1, min(int(limit), 100))]

def save_feedback(profile_id: str, record_id: str, suggestion_title: str, rating: str, comment: str = "") -> dict[str, Any]:
    if not _valid_id(profile_id):
        raise ValueError("profile_id may contain only letters, digits, hyphen and underscore")
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", record_id):
        raise ValueError("record_id is invalid")
    if not any(r.get("record_id") == record_id for r in list_meal_records(profile_id, 100)):
        raise LookupError("Meal record was not found for this profile")
    item = {"feedback_id": str(uuid.uuid4()), "record_id": record_id, "profile_id": profile_id,
            "suggestion_title": suggestion_title[:160], "rating": rating,
            "comment": comment[:1000], "created_at": datetime.now(timezone.utc).isoformat()}
    path = RECORD_DIR / f"{profile_id}_feedback.json"
    rows = _read(path)
    rows.insert(0, item)
    _write(path, rows[:1000])
    return item

def list_feedback(profile_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    if not _valid_id(profile_id):
        raise ValueError("profile_id may contain only letters, digits, hyphen and underscore")
    return _read(RECORD_DIR / f"{profile_id}_feedback.json")[:max(1, min(int(limit), 2000))]
