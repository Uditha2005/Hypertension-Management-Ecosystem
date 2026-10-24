# New DASH ML model training report

Training was run on paired Day 1 and Day 2 food-group servings from the supplied Dietary Behavior Dataset. 4,650 paired participants were available. Day 1 food-group servings are inputs; Day 2 servings are targets. Participants were split 70/15/15 into train/validation/test with random_state=42.

| Candidate | Validation MAE (servings/group) | Validation variance-weighted R² |
|---|---:|---:|
| model        |   validation_mae |   validation_r2 |   fit_seconds |
|:-------------|-----------------:|----------------:|--------------:|
| Ridge        |         0.433321 |        0.171327 |          0.32 |
| RandomForest |         0.443034 |        0.150916 |          2.91 |
| ExtraTrees   |         0.441989 |        0.154922 |          1.39 |

Selection: Ridge multi-output regression, selected among the three actual ML candidates because it had the highest validation variance-weighted R². The held-out test result was MAE 0.4344 and variance-weighted R² 0.1751. The model has limited predictive power. It predicts observed next-day behaviour, not diet quality. The live endpoint blends 30% model-predicted profile with 70% mapped current intake, then applies the existing DASH optimizer. This is an experimental integration and requires additional validation.
