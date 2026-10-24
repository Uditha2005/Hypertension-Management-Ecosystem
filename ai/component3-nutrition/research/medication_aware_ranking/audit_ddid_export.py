"""Profile a downloaded DDID interaction export and extract medicine-related review candidates.

This tool preserves original DDID columns and adds audit metadata. It does not turn
DDID records into app warnings: records need field-level interpretation, source review,
active-ingredient confirmation, and qualified review before promotion to the runtime registry.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import pandas as pd

MEDICINES = [
    "ramipril", "spironolactone", "irbesartan", "losartan", "amlodipine",
    "nifedipine", "verapamil", "clopidogrel", "metoprolol", "indapamide",
    "ezetimibe", "enalapril", "aspirin", "carvedilol", "bisoprolol", "atenolol",
    "telmisartan", "perindopril", "lisinopril", "valsartan", "candesartan",
    "hydrochlorothiazide", "bendroflumethiazide", "diltiazem", "atorvastatin",
]


def load_csv(path: Path) -> pd.DataFrame:
    errors = []
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding, low_memory=False)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError("Could not decode CSV; tried UTF-8, GB18030 and Latin-1. " + "; ".join(errors))


def audit(path: Path) -> tuple[pd.DataFrame, dict]:
    df = load_csv(path)
    if df.empty and len(df.columns) == 0:
        raise ValueError("The file has no readable columns. Check that the DDID interaction CSV was downloaded.")
    # Search all fields rather than assuming a specific export schema. Original fields remain intact.
    combined = df.astype(str).agg(" | ".join, axis=1).str.casefold()
    matched_terms = {}
    mask = pd.Series(False, index=df.index)
    for drug in MEDICINES:
        drug_mask = combined.str.contains(rf"(?<![a-z]){re.escape(drug)}(?![a-z])", regex=True, na=False)
        if drug_mask.any():
            matched_terms[drug] = int(drug_mask.sum())
            mask |= drug_mask
    candidates = df.loc[mask].copy()
    candidates.insert(0, "ddid_source_row_number", candidates.index + 2)  # CSV line incl. header
    candidates["local_medicine_keyword_matches"] = [
        "; ".join(drug for drug in MEDICINES if re.search(rf"(?<![a-z]){re.escape(drug)}(?![a-z])", " | ".join(map(str, row)).casefold()))
        for row in candidates.drop(columns=["ddid_source_row_number"], errors="ignore").itertuples(index=False, name=None)
    ]
    candidates["review_status"] = "unreviewed_candidate_not_for_runtime"
    candidates["runtime_promotion_allowed"] = "no"
    report = {
        "status": "source_profiled_review_candidates_only",
        "input_filename": path.name,
        "rows_total": int(len(df)),
        "columns_total": int(len(df.columns)),
        "column_names": list(map(str, df.columns)),
        "rows_matching_supported_or_related_medicine_terms": int(mask.sum()),
        "matched_medicine_terms_and_row_counts": matched_terms,
        "candidate_output_preserves_all_original_columns": True,
        "runtime_rules_added": 0,
        "important_limitations": [
            "Keyword matches are candidates for manual review, not confirmed clinical interactions.",
            "This script does not infer interaction direction, severity, dose, food form, or clinical applicability.",
            "Records must be inspected with source/reference details and reviewed before any app warning is created.",
            "A missing keyword match is not evidence that an interaction does not exist.",
            "DDID food/herb interaction records may not directly apply to the app's food items or local medication formulations.",
        ],
    }
    return candidates, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to downloaded DDID Interaction Information.csv")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("results") / "ddid_audit")
    args = parser.parse_args()
    if not args.input.exists():
        parser.error(f"input file does not exist: {args.input}")
    candidates, report = audit(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.output_dir / "ddid_medicine_review_candidates.csv", index=False)
    (args.output_dir / "ddid_export_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
