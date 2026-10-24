# DASH optimizer and ML preference model

## Current implementation

The live `POST /dash/optimize-current-day` workflow uses two components:

1. **New ML component:** a trained Ridge multi-output regression model predicts Day 2 food-group servings from Day 1 food-group servings in paired NHANES dietary records. At inference, its predicted profile is blended at 30% with the user's mapped current-day profile.
2. **Existing DASH optimizer:** projects that blended profile against the supplied aggregate food-group nutrient constraints. The optimizer remains in place and returns optional serving changes.

The ML target is *observed next-day dietary behaviour*. It is not a meal-suitability label, a measure of diet quality, a causal preference, or a clinical outcome. This model is experimental and must not be presented as clinically validated.

## Dataset and training

Dataset: `data_source/Dietary-Behavior-Dataset-master.zip`, supplied Dietary Behavior Dataset based on NHANES Day 1 and Day 2 food-consumption records. Training uses paired participants with food-group servings on both days. No synthetic patient records are created.

Reproduce comparison and training from the repository root:

```bash
python ai/component3-nutrition/research/dash_servings/src/train_ml_preference_model.py
```

The script compares Ridge, Random Forest and Extra Trees using a participant-level 70/15/15 train/validation/test split (`random_state=42`). Selection uses validation variance-weighted R² among the ML candidates; the test set is held out until after selection. Results are in `results/new_ml_training/`; the fitted artifact is in `models/dash_next_day_preference_ridge.joblib`.

## Current evaluation

- Paired participants: 4,650
- Outputs: 50 food-group serving targets
- Selected model: Ridge multi-output regression
- Validation MAE: 0.4333 servings per food group
- Validation variance-weighted R²: 0.1713
- Held-out test MAE: 0.4344 servings per food group
- Held-out test variance-weighted R²: 0.1751

These results indicate limited predictive signal. The model was selected as the strongest R² among the three tested ML candidates, not because it is proven to generate healthy recommendations. Compare model metrics before relying on this output.

## Removed legacy experiment

The previous demographic-to-average-serving regression experiment compared DummyMedian, HistGradientBoosting, Random Forest and Extra Trees. It was removed from active code and its detailed result files were deleted because it performed poorly and did not directly model meal suitability. Its existence and purpose are recorded here for project history. The new model above is a separate Day-1-to-Day-2 dietary-pattern experiment.

## Limitations

- The dataset reflects observed intake; it does not label ideal or healthier replacement meals.
- The 30% prediction blend is a conservative integration choice, not a learned or clinically validated parameter.
- Food-to-group mapping is keyword-based and may misclassify foods.
- Nutrient coefficients and bounds are aggregate research constraints, not personalized clinical prescriptions.
- The model/optimizer combination requires broader evaluation and dietitian review before any health claims.
