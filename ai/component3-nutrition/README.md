# Component 3: Hypertension Dietary Risk Assessment System

Part of the AI-Powered Hypertension Management Ecosystem (project J26-SE-312).

## Agreed system workflow

1. Caregiver enters meal foods, quantities and relevant resident information.
2. USDA FoodData Central records are used to calculate nutrient totals.
3. A trained ML model returns an **exploratory BP-associated category estimate** based on resident characteristics and average daily dietary features.
4. A separate nutrient assessment highlights selected dietary concerns (currently sodium relative to a general adult reference).
5. The UI displays approximate model-feature sensitivity explanations to help users understand model behaviour.

**Important:** the trained model predicts an NHANES BP-associated category. It is not trained on meal-suitability labels and does not directly determine whether a meal is suitable, diagnose hypertension, prove causality, or predict future BP changes. Model output and nutrient-reference checks are deliberately presented separately.

## Research core

The research pipeline compares demographic-only features against dietary-enhanced features and compares Logistic Regression, Random Forest, Extra Trees and RBF SVM. The selected application model is chosen by five-fold CV macro-F1 among models using demographic + Day 1 dietary features. The feature-set comparison also includes a two-day dietary mean.

The research cohort is adults aged 60–80, consistent with the elderly-care focus. BP readings are used only to create the target label and are not model inputs. NHANES contains observed 24-hour dietary recalls, not a planned seven-day intake record.

## Run the model experiment

From the repository root:

```bash
source ai/venv/bin/activate
python ai/component3-nutrition/src/run_final_training_experiment.py
python -m pytest ai/component3-nutrition/tests -q
```

The script writes model comparison results and an evaluation report to
`ai/component3-nutrition/results/final_training/` and the selected pipeline to
`ai/component3-nutrition/models/selected_daily_intake.joblib`.

## Run the application

Install the Python dependencies from `ai/component3-nutrition/requirements.txt`,
configure `USDA_FDC_API_KEY` for USDA lookups, and start the API using the
project's existing startup instructions. The React UI is under
`frontend/web/`.

## Dietary reference and limitations

The sodium check uses 2,300 mg/day as a general adult reference, not an
individualised medical prescription. It assesses only foods entered for each
date; omitted foods can change the result. Model class probabilities are not
calibrated clinical risk probabilities. The existing holdout was examined in
earlier project experiments, so the recorded test metrics are exploratory.
