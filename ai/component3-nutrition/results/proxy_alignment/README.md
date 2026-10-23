# Daily nutrient-reference alignment proxy experiment

This experiment makes model training possible using real NHANES Day 1 dietary records, without fabricating observations. The target is explicitly **rule-derived weak supervision**: a daily record is `reference_aligned_proxy` if sodium is <= 2300 mg/day and saturated-fat energy share is <= 6%; otherwise it is `needs_review_proxy`.

These are proxy labels generated from documented thresholds, **not** expert-reviewed labels, ground truth, clinical outcomes, or meal-level suitability. Sodium, saturated fat, and energy are excluded from model predictors because they define the proxy label. Four candidate classifiers are compared using participant-grouped cross-validation; a held-out participant set is used for final metrics.

The experiment is useful as a methodological/weak-supervision component, but its results must not be described as clinically validated meal-suitability prediction. The app's transparent nutrient assessment remains the primary meal-level feature.

Run from the repository root:
```bash
python ai/component3-nutrition/src/train_proxy_alignment_models.py
```
