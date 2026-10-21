# Component 3 — Next-Stage Research Evaluation

## Scope

This diagnostic compares Extra Trees feature sets on the same two-day-complete participants and separately evaluates participants aged 60+. It does not change the production model.

- All-adult matched cohort: **n=6470**
- Adults aged 60+ matched cohort: **n=2241**

## Cross-validation results

| Cohort | Feature set | Mean fold macro-F1 | Fold SD | Pooled OOF macro-F1 |
|---|---|---:|---:|---:|
| all_adults_two_day_complete | demographic_only | 0.352 | 0.011 | 0.352 |
| all_adults_two_day_complete | demographic_day1 | 0.365 | 0.018 | 0.365 |
| all_adults_two_day_complete | demographic_2day_mean | 0.379 | 0.010 | 0.379 |
| adults_60_plus_two_day_complete | demographic_only | 0.276 | 0.020 | 0.276 |
| adults_60_plus_two_day_complete | demographic_day1 | 0.285 | 0.010 | 0.286 |
| adults_60_plus_two_day_complete | demographic_2day_mean | 0.316 | 0.019 | 0.316 |

## Held-out category performance

See `next_eval_per_category.csv` and `next_eval_confusion_long.csv`. Focus on per-category recall and support, not just overall accuracy.

## Paired cross-validation differences

See `next_eval_paired_cv_deltas.csv`. Positive deltas mean the compared dietary feature set scored higher than demographics-only on that same fold. With only five folds, treat these differences as descriptive rather than definitive statistical proof.

## Interpretation cautions

- This is a targeted diagnostic, not a final model-selection decision.
- The existing holdout is exploratory, not untouched confirmatory evidence.
- A two-day average does not validate planned weekly meals.
- Confirm BP label thresholds against the guideline version specified in the approved proposal.
- If a feature set wins in cross-validation, further validation is still required before replacing the application model.
