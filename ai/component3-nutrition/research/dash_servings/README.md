# DASH daily food-group serving research

## Defined prediction target

Predict **average observed servings per food group across NHANES dietary Day 1 and Day 2** from age, sex, and self-reported hypertension. This target is available from the supplied dietary dataset and does not require fabricated labels.

It is a behavioural regression target, not personalized meal suitability, clinical risk, or a recommendation label. The meal-suitability classifier pipeline remains separate and blocked until genuine labelled meals with provenance are supplied.

## Four-model comparison

Run from repository root:

```bash
python ai/component3-nutrition/research/dash_servings/src/train_compare_servings.py
```

The script builds participant-level records from the original dataset, uses a fixed 70/15/15 train/validation/test split, chooses the candidate by lowest validation MAE, refits the selected model on train+validation, and evaluates once on the held-out test set. The four candidates are DummyMedian, RandomForest, ExtraTrees, and HistGradientBoosting (multi-output). No synthetic data are generated.

## Current recorded results

Validation MAE (servings per food group):
- DummyMedian: **0.352427** (selected)
- HistGradientBoosting: 0.424936
- RandomForest: 0.430866
- ExtraTrees: 0.431213

Held-out test for the selected median baseline:
- MAE: **0.344729 servings per food group**
- Variance-weighted R²: **-0.102117**

Negative variance-weighted R² means the selected model does not explain held-out variation better than a mean-like baseline under this metric. Do not describe these results as strong predictive performance. The target is sparse and many food-group targets are zero for many participants.

Participant counts, exact split, model columns, and target definition are in `results/training/training_manifest.json`; per-model metrics are in `results/training/four_model_validation_comparison.csv`; held-out metrics are in `results/training/heldout_test_summary.csv`.

## Daily DASH optimization

`src/dash_optimizer.py` implements a feasibility-checked constrained projection. Coefficients and bounds are copied from the supplied Dietary Behavior Dataset research package. The optimizer is intended for daily food-group serving profiles. It does not optimize a single meal and does not establish clinical suitability. See the included optimization evaluation report in `reports/`.

## Source and use

The original dataset archive is preserved in `data_source/Dietary-Behavior-Dataset-master.zip`. Cite Ahmadi, Ganjkhanloo, and Ghobadi (2020), *An Open-Source Dataset on Dietary Behaviors and DASH Eating Plan Optimization Constraints*, arXiv:2010.07531. Review original dataset license/terms before redistribution or external reuse.
