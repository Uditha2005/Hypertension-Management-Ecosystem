# Component 3 — Final Candidate Comparison

## Purpose
Compare balanced Extra Trees with the `target_115` weighting strategy using existing development-partition cross-validation outputs.
This script performs no training, does not score the existing holdout, and does not save or replace a model.

## Summary

| Cohort | Strategy | CV macro-F1 mean | Fold SD | Pooled OOF macro-F1 | Pooled OOF accuracy |
|---|---|---:|---:|---:|---:|
| Adults aged 60+ | balanced_baseline | 0.316 | 0.018 | 0.317 | 0.335 |
| Adults aged 60+ | target_115 | 0.292 | 0.013 | 0.293 | 0.296 |
| All adults | balanced_baseline | 0.377 | 0.009 | 0.377 | 0.434 |
| All adults | target_115 | 0.379 | 0.008 | 0.379 | 0.415 |

## Elevated and Stage 1 performance

| Cohort | Strategy | Category | Precision | Recall | F1 |
|---|---|---|---:|---:|---:|
| Adults aged 60+ | balanced_baseline | Elevated | 0.189 | 0.219 | 0.203 |
| Adults aged 60+ | target_115 | Elevated | 0.171 | 0.278 | 0.212 |
| Adults aged 60+ | balanced_baseline | Stage 1 | 0.274 | 0.270 | 0.272 |
| Adults aged 60+ | target_115 | Stage 1 | 0.240 | 0.331 | 0.278 |
| All adults | balanced_baseline | Elevated | 0.191 | 0.208 | 0.199 |
| All adults | target_115 | Elevated | 0.193 | 0.298 | 0.234 |
| All adults | balanced_baseline | Stage 1 | 0.302 | 0.265 | 0.283 |
| All adults | target_115 | Stage 1 | 0.285 | 0.345 | 0.312 |

## Interpretation rules
- Do not select a candidate using only accuracy; review macro-F1 and all four categories.
- `target_115` may improve Elevated/Stage 1 recall while reducing precision or other-category performance.
- Compare adults aged 60+ separately; a candidate that leads in all adults need not lead in the older subgroup.
- These are exploratory CV results on a dataset used in prior experiments, not untouched confirmatory evidence.
- NHANES recalls represent observed intake, not planned meals. This classifier is not causal and does not forecast future BP.
- No candidate is deployed by this script. Keep the production model unchanged until the team explicitly validates a replacement.

## Generated files
- `final_candidate_summary.csv`
- `final_candidate_per_category.csv`
- `final_candidate_deltas.csv`
- `final_candidate_confusion_long.csv`
