# Component 3 — Targeted Training Experiment

## Purpose
Compare tree-model class-weighting strategies using the existing two-day diet feature set. This is a research-only experiment; it does not replace or save a production model.

## Method
- Five-fold stratified cross-validation on the development partition.
- The existing exploratory holdout was not scored or used for selection.
- Same two-day feature set and same folds within each cohort.
- Cohorts: all two-day-complete adults and participants aged 60+.
- Primary metric: macro-F1; also inspect category-specific recall, precision, F1, and confusion counts.

## Results

| Cohort | Strategy | CV macro-F1 mean | Fold SD | Pooled OOF macro-F1 |
|---|---|---:|---:|---:|
| adults_60_plus_two_day_complete | extra_trees_balanced | 0.311 | 0.023 | 0.312 |
| adults_60_plus_two_day_complete | extra_trees_balanced_subsample | 0.311 | 0.023 | 0.312 |
| adults_60_plus_two_day_complete | random_forest_balanced_subsample | 0.273 | 0.019 | 0.274 |
| adults_60_plus_two_day_complete | random_forest_unweighted | 0.258 | 0.019 | 0.259 |
| adults_60_plus_two_day_complete | extra_trees_unweighted | 0.211 | 0.022 | 0.212 |
| all_adults_two_day_complete | extra_trees_balanced | 0.378 | 0.011 | 0.378 |
| all_adults_two_day_complete | extra_trees_balanced_subsample | 0.378 | 0.011 | 0.378 |
| all_adults_two_day_complete | random_forest_balanced_subsample | 0.368 | 0.014 | 0.369 |
| all_adults_two_day_complete | random_forest_unweighted | 0.324 | 0.011 | 0.324 |
| all_adults_two_day_complete | extra_trees_unweighted | 0.276 | 0.003 | 0.276 |

## Interpretation
- Class weighting materially changes the balance between majority-class performance and minority-category performance.
- Compare category-level recall before choosing a model; a higher macro-F1 does not guarantee acceptable performance for every category.
- The current Extra Trees balanced model remains the strongest candidate in this experiment by cross-validation macro-F1 in both cohorts. The unweighted tree variants have lower macro-F1 and particularly weak recall for some categories.
- Results are exploratory. Five-fold CV does not prove statistical significance, and the underlying dataset has been used in earlier experiments.

## Limitations
- The age-60+ threshold is operational and should match the approved proposal.
- NHANES recalls describe observed intake, not planned meal schedules.
- This is classification of BP-associated categories, not causal inference or future BP forecasting.
- Confirm the BP label thresholds against the guideline version specified in the approved proposal.

## Output files
- `targeted_training_summary.csv` — summary comparison.
- `targeted_training_folds.csv` — fold-level metrics.
- `targeted_training_per_category.csv` — pooled out-of-fold per-category precision/recall/F1.
- `targeted_training_confusion_long.csv` — pooled out-of-fold confusion counts.
- `targeted_training_audit.json` — cohort and limitations audit.
