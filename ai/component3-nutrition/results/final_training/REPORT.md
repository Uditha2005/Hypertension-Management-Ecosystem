# Component 3 — Controlled Model Training Experiment

## Purpose
Compare four classifiers and three feature sets on a matched older-adult NHANES cohort. The production candidate is selected only among daily-intake (Day 1) models to match a one-day planned-intake interface.

## Dataset and protocol
- Matched complete cohort, ages 60–80: **2241** participants.
- Development partition: **1792**; stratified holdout: **449**.
- Five-fold stratified cross-validation on the development partition; identical folds for every candidate.
- The held-out split has been inspected in earlier project work, so its metrics are exploratory rather than independent confirmation.
- BP measurement variables are not model features; they are only represented by the target label.

## Cross-validation results
| Feature set | Model | Mean CV macro-F1 | Fold SD |
|---|---|---:|---:|
| demographic_2day_mean | rbf_svm | 0.3073 | 0.0200 |
| demographic_2day_mean | extra_trees | 0.3043 | 0.0273 |
| demographic_day1 | rbf_svm | 0.2969 | 0.0316 |
| demographic_2day_mean | logistic_regression | 0.2945 | 0.0277 |
| demographic_only | logistic_regression | 0.2920 | 0.0197 |
| demographic_day1 | extra_trees | 0.2899 | 0.0105 |
| demographic_only | rbf_svm | 0.2891 | 0.0126 |
| demographic_day1 | logistic_regression | 0.2837 | 0.0112 |
| demographic_2day_mean | random_forest | 0.2794 | 0.0215 |
| demographic_only | extra_trees | 0.2739 | 0.0211 |
| demographic_only | random_forest | 0.2630 | 0.0212 |
| demographic_day1 | random_forest | 0.2580 | 0.0187 |

## Selected daily-intake model
- Model: **rbf_svm**
- Day-1 feature-set mean CV macro-F1: **0.2969**
- Exploratory holdout macro-F1: **0.3031**
- Exploratory holdout accuracy: **0.3163**

## Class-level results
| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Normal | 0.324 | 0.388 | 0.353 | 116 |
| Elevated | 0.214 | 0.300 | 0.250 | 80 |
| Stage 1 | 0.226 | 0.200 | 0.212 | 95 |
| Stage 2 | 0.474 | 0.342 | 0.397 | 158 |

## Interpretation and limits
The selected model predicts BP-associated categories from age, sex, BMI and daily dietary features. It does not predict meal suitability, prove causation, diagnose hypertension, or estimate future BP changes. Nutrient-reference checks are displayed separately from the model prediction. Because the data are observational and the holdout has prior exposure, all results are exploratory.
