# DDID interaction evidence review workflow

## Why this exists

DDID is a public, manually curated diet–drug interaction resource. Its website lists downloadable drug, food, herb, and interaction files, and its 2024 paper describes 23,950 interaction records. The supplied DDID export has now been audited. A prioritized review queue and summary are stored in `results/ddid_import/`. The runtime registry remains the small, source-linked set of selected official patient-guidance reminders; DDID rows have not been automatically promoted into patient-facing rules.

- Download page: https://bddg.hznu.edu.cn/ddid/download/
- Primary paper: Hong et al., *Briefings in Bioinformatics* (2024), DOI: https://doi.org/10.1093/bib/bbae212

## Import and audit the public export

1. Open the DDID download page and download **Food/Herb-Drug Interaction General Information** (`Interaction Information.csv`).
2. Keep the original file unchanged in a private research-data folder; do not commit it unless its licence and redistribution terms have been checked.
3. Run from the repository root:

```bash
python ai/component3-nutrition/research/medication_aware_ranking/audit_ddid_export.py \
  --input /path/to/Interaction\ Information.csv
```

The audit script writes a keyword-screened queue. The current supplied export has additionally been screened by exact normalized medicine names and saved as `results/ddid_import/ddid_prioritized_review_queue.csv`, with summary at `ddid_prioritized_review_summary.json`. Its triage bands prioritize food records with human-context and reference fields for review; the score is not a clinical risk score. Original source fields and source-row numbers are retained.

## Manual evidence-review worksheet

For every candidate record selected for consideration, document:

- DDID record/source identifier and export date/version;
- exact drug name and confirmed active ingredient, including salts/formulation if applicable;
- food/herb and form (e.g., juice versus whole food), dose/exposure, and experimental/clinical context;
- DDID interaction category and direction exactly as represented by the source;
- linked primary reference and whether it supports patient-facing advice;
- evidence reviewer, second reviewer, decision, rationale, date, and unresolved questions;
- whether it is approved for research-only analysis or separately approved for a user-facing precaution.

Do not convert a database association directly into a warning. Do not interpret an absent record as evidence of no interaction. A qualified reviewer should check any proposed patient-facing rule against current official product information or authoritative patient guidance. Keep rule activation conservative and separate from the learned suggestion-ranking model.

## Recommendation-ranking dataset: how to obtain real labels

The blank `training_examples_template.csv` remains a schema, not observations. To collect real labels, create pseudonymous participant/context IDs and show independent reviewers several eligible candidate suggestions for each context. Each candidate should have its own evidence source ID and a 0–3 relevance label using `ANNOTATION_GUIDE.md`. Reviewers must be blinded to the current baseline rank where practical and should not simply copy the rule score. Record reviewer identity as a study code, disagreements, adjudication, and exclusion reasons in a separate controlled file. Do not place names, full dates of birth, medical record numbers, or other direct identifiers in the modelling CSV.

Keep all safety-ineligible candidates out of the ranker and separately measure safety-filter false positives/negatives. Use participant-grouped train/validation/test splits, compare against the existing transparent baseline, and report NDCG@3 on expert labels. The current training script's minimum data requirements are a prototype gate, not a guarantee of statistical power or clinical validity.

## Import results from the supplied DDID export (2026-10-23)

The uploaded `Interaction Information.csv` was successfully parsed locally. It contains 23,950 rows and 26 columns, with 1,510 unique drug names and 1,385 unique food/herb names. The `Type` field has 4,865 Food records and 19,085 Herb records. Relationship classifications are mixed (including HFDI, Drugbank, and package-insert categories), so they must not be treated as a single uniform evidence grade.

The audit script selected 3,194 rows across 17 medicine-name candidates from its deliberately limited hypertension/antiplatelet/anticoagulant term list. Only 128 of those rows also matched the simple food-keyword list. These are keyword-based triage counts, not confirmed clinical interactions. Many candidate rows involve herbs, animal studies, or foods unrelated to the intended trigger; reviewer screening is required.

Generated files:
- `results/ddid_import/ddid_import_audit.json`: aggregate counts and provenance note.
- `results/ddid_import/ddid_hypertension_medicine_review_queue.csv`: source fields retained, with blank reviewer decision fields. Do not load this review queue into the live warning registry.

Re-run:
```bash
python research/medication_aware_ranking/audit_ddid_interactions.py /path/to/Interaction\ Information.csv --out-dir research/medication_aware_ranking/results/ddid_import
```
The script intentionally does not generate approved patient messages or change `medication_food_interactions.json`.


## Ready-to-fill expert annotation batch

Use `expert_annotation_batch_template.csv` to record one candidate suggestion per participant/meal context. `candidate_suggestion_catalog_for_annotation.csv` provides suggestion wording candidates only; these are not participant records and carry no labels. Reviewers must judge each suggestion against an actual, documented context, and may leave labels blank when context or evidence is insufficient. Do not train until the minimum participant/context thresholds in `src_train_ranker.py` are met.


## Human-food evidence priority batch

The generated file `results/ddid_import/human_food_evidence_priority_batch.csv` filters the supplied DDID export to candidate records that match the targeted medicine-name list, have `Type=Food`, have a human-species label, and include a PMID or DOI. This is a reproducible screening filter, not a completed literature review. Every row is marked `NOT_REVIEWED` and `DO_NOT_ACTIVATE_UNTIL_REVIEWED`. Reviewers must open the original paper, verify population, dose/form, design, outcome and applicability to ordinary food consumption, and record a reasoned disposition. A DOI/PMID field alone does not establish source accuracy or clinical significance.

## Recommendation-ranking labels

The suggestion-rating template remains an empty collection instrument. Do not treat suggested labels, generated examples, or the DDID interaction rows as relevance labels for nutrition recommendations. The ranker must remain untrained until independent reviewers provide actual ratings tied to documented meal contexts. After collection, use participant/context-grouped train/validation/test splits, compare against the rule-based baseline, and report ranking metrics with confidence intervals where sample size permits.
