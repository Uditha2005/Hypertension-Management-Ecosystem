# Component 3: Rebuilt research pipeline notes

## Why this rebuild exists
The original proposal asks whether dietary information adds useful information beyond demographic features for BP-associated category classification. The prior experiments did not cleanly isolate this question because the multi-day feature columns could contain a Day-1-only mean when Day 2 was missing, and not all feature comparisons were explicitly restricted to identical participants.

## Changes in this research version
- Reconstructs a new dataset from the bundled NHANES 2017–March 2020 XPT source files.
- Applies the Day 1 reliable recall rule and explicitly records Day 2 recall validity.
- Calculates two-day nutrient means only when valid nutrient values exist for both days.
- Keeps BP readings solely for label construction; they are excluded from all predictors.
- Compares demographic-only and dietary-enhanced models on matched participant cohorts.
- Fits imputation and scaling inside each CV fold through sklearn pipelines.
- Writes new data and results into separate `rebuilt/` folders; does not overwrite legacy processed data, saved production model, or old research outputs.

## Preliminary findings
See `results/rebuilt_research/cv_summary.csv`, `cv_folds.csv`, `holdout_summary.csv`, and `dataset_audit.json`. On the matched complete-two-day cohort, adding dietary features improved mean CV macro-F1 for all three tested models relative to demographic-only features, but the size and consistency of gains vary. Day-1 diet also showed mixed gains on the Day-1 cohort. This is preliminary evidence, not a causal result and not proof that planned meal plans will generalize.

The held-out split is exploratory only: this dataset has already been used in earlier experiments. It must not be described as a pristine final test set. A future confirmatory test requires a genuinely untouched external cohort or a prospectively locked dataset. The chosen BP-category threshold rule should be verified against the guideline version approved for the final proposal.

## Run locally
From the repository root:

```bash
source ai/venv/bin/activate
python ai/component3-nutrition/src/rebuild_research_pipeline.py
```

Run tests:

```bash
source ai/venv/bin/activate
python -m pytest ai/component3-nutrition/tests -q
```

This is a research-only pipeline. Do not replace the application's selected XGBoost model until the results have been reviewed and the prediction interface has been checked for feature compatibility.
