#!/usr/bin/env python3
"""Audit DDID Food/Herb-Drug Interaction General Information CSV.

This tool preserves source records and produces a *review queue*, not clinical advice.
No imported record is promoted automatically to the patient-facing rule registry.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import pandas as pd

MEDICINE_TERMS = [
    "amlodipine", "nifedipine", "verapamil", "losartan", "valsartan",
    "irbesartan", "ramipril", "lisinopril", "enalapril", "spironolactone",
    "hydrochlorothiazide", "furosemide", "metoprolol", "propranolol",
    "atenolol", "clopidogrel", "warfarin"
]
FOOD_TERMS = [
    "grapefruit", "pomelo", "pomegranate", "banana", "potassium", "salt substitute",
    "licorice", "liquorice", "high sodium", "salt", "alcohol", "food"
]
REQUIRED = ["Drug_Name", "Food_Herb_Name", "Type", "Result", "Effect", "Conclusion",
            "Reference", "Relationship_classification"]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    args=ap.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(args.csv, dtype=str, keep_default_na=False, low_memory=False)
    missing=[c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit("Missing expected DDID columns: "+", ".join(missing))
    lower_drug=df["Drug_Name"].str.lower()
    lower_food=df["Food_Herb_Name"].str.lower()
    meds=lower_drug.apply(lambda x: any(re.search(r"(?<![a-z])"+re.escape(t)+r"(?![a-z])",x) for t in MEDICINE_TERMS))
    food=lower_food.apply(lambda x: any(t in x for t in FOOD_TERMS))
    # Prioritise exact medication-name candidates and foods that may be relevant,
    # but retain every matching medication record for human review.
    cand=df.loc[meds].copy()
    cand.insert(0,"DDID_Source_Row", cand.index + 2) # CSV row number including header
    cand["Review_Priority"] = [
        "review-food-and-medicine-match" if bool(food.loc[i]) else "review-medicine-match"
        for i in cand.index
    ]
    for c in ["Reviewer_Status","Clinical_Interpretation","Approved_Patient_Message","Reviewer_Name","Review_Date"]:
        cand[c]=""
    cand.to_csv(args.out_dir/"ddid_hypertension_medicine_review_queue.csv",index=False)
    summary={
        "input_file": args.csv.name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "unique_drug_names": int(df["Drug_Name"].nunique()),
        "unique_food_herb_names": int(df["Food_Herb_Name"].nunique()),
        "relationship_classification_counts": df["Relationship_classification"].value_counts().to_dict(),
        "type_counts": df["Type"].value_counts().to_dict(),
        "experimental_species_counts_top_10": df["Experimental_Species"].replace("",pd.NA).value_counts().head(10).to_dict() if "Experimental_Species" in df else {},
        "medicine_candidate_rows": int(len(cand)),
        "candidate_unique_medicines": int(cand["Drug_Name"].nunique()),
        "candidate_unique_food_herbs": int(cand["Food_Herb_Name"].nunique()),
        "candidate_rows_with_food_keyword_match": int(sum(food.loc[i] for i in cand.index)),
        "candidate_medicine_counts": cand["Drug_Name"].value_counts().to_dict(),
        "safety_note": "Candidate matches are not validated clinical warnings. Check the original reference, species, dose, study design, result, and clinical relevance before approving any user-facing message."
    }
    (args.out_dir/"ddid_import_audit.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ["rows","unique_drug_names","unique_food_herb_names","medicine_candidate_rows","candidate_unique_medicines","candidate_rows_with_food_keyword_match"]},indent=2))
if __name__=="__main__":
    main()
