"""Create a transparent coverage report for catalogue labels vs. the local evidence registry.

This is a coverage audit only. It does not confirm a patient's prescription, establish
that all interactions are known, or infer that no interaction exists when no rule matches.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOGUE = Path(__file__).with_name("medication_catalogue_coverage_template.csv")
DEFAULT_REGISTRY = ROOT / "src" / "medication_food_interactions.json"


def audit(catalogue_path: Path, registry_path: Path) -> tuple[pd.DataFrame, dict]:
    catalogue = pd.read_csv(catalogue_path, dtype=str).fillna("")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    rules = registry.get("rules", [])
    rows = []
    for _, item in catalogue.iterrows():
        candidate = item.get("candidate_active_ingredient_not_yet_confirmed", "").strip().casefold()
        matched_rules = [rule for rule in rules if candidate and rule.get("active_ingredient", "").casefold() == candidate]
        rows.append({
            "catalogue_label": item.get("catalogue_label_from_screenshot", ""),
            "candidate_active_ingredient": candidate,
            "catalogue_normalization_status": item.get("normalization_status", ""),
            "prescription_confirmation_status": "not_confirmed_by_this_audit",
            "local_evidence_rule_count": len(matched_rules),
            "covered_trigger_categories": "; ".join(sorted({rule["id"].split("-")[-1] for rule in matched_rules})),
            "evidence_source_urls": " ; ".join(sorted({rule.get("source_url", "") for rule in matched_rules if rule.get("source_url")})),
            "interpretation": (
                "Candidate ingredient has one or more source-linked rules; confirm prescription and review scope."
                if matched_rules else
                "No local rule for this candidate ingredient; this does NOT mean no interaction exists."
                if candidate else
                "Ingredient unresolved; verify packaging/prescription before interaction matching."
            ),
        })
    output = pd.DataFrame(rows)
    report = {
        "status": "partial_coverage_only",
        "catalogue_labels": int(len(output)),
        "labels_with_candidate_ingredient": int(output["candidate_active_ingredient"].ne("").sum()),
        "labels_with_at_least_one_local_rule": int(output["local_evidence_rule_count"].gt(0).sum()),
        "labels_unresolved": int(output["candidate_active_ingredient"].eq("").sum()),
        "local_rule_count": int(len(rules)),
        "registry_last_reviewed": registry.get("last_reviewed"),
        "important_limitations": [
            "Catalogue labels are not a confirmed patient's prescription list.",
            "Candidate active ingredients still require verification against packaging or a reviewed prescription.",
            "The local registry is intentionally partial and currently contains selected food-triggered reminders only.",
            "No match is not evidence that a medicine has no food interactions.",
            "This report counts local rules, not all DDID records or clinically validated interactions.",
        ],
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-csv", type=Path, default=Path(__file__).with_name("results") / "catalogue_interaction_coverage.csv")
    parser.add_argument("--output-json", type=Path, default=Path(__file__).with_name("results") / "interaction_coverage.json")
    args = parser.parse_args()
    table, report = audit(args.catalogue, args.registry)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_csv, index=False)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
