# Component 3: Hypertension Dietary Risk Assessment System

Part of the AI-Powered Hypertension Management Ecosystem (project J26-SE-312).

## Purpose
This component converts caregiver-entered multi-day meal plans into quantitative dietary features and uses a model trained on NHANES data to give a BP-associated classification for elderly care-home residents. It is designed to support caregiver decision-making and does not give medical treatment advice.

## Key functions

### Function 1: NHANES-based BP category classifier (research core)
Compares demographic-only features (age, sex, BMI) against dietary-enhanced features to measure whether dietary information improves BP-associated classification. The four target categories are Normal, Elevated, Stage 1 hypertension and Stage 2 hypertension.

**Inputs**
- NHANES 2017-March 2020 data: demographics, body measures, oscillometric blood pressure, and Day 1 and Day 2 dietary recalls.
- Demographic-only features: age, sex, BMI.
- Dietary-enhanced features: the demographic features plus sodium, potassium, sodium-to-potassium ratio, energy and saturated fat (Day 1, and a multi-day mean where available).

**Outputs**
- A trained BP category classifier (Logistic Regression, Random Forest and XGBoost are compared).
- An evaluation of demographic-only against dietary-enhanced models using accuracy, precision, recall, macro-F1 and confusion matrices.

**Notes**
- The BP readings are used only to create the target category. They are never used as model inputs.
- NHANES provides 24-hour recalls (Day 1 and Day 2), not a seven-day record. The model is trained only on these recalls.

### Function 2: Meal-plan processing module
Turns caregiver-entered foods and quantities into daily and weekly nutrient summaries.

**Inputs**
- Caregiver-entered foods and quantities from a weekly meal plan.
- Food and nutrient records from USDA FoodData Central.

**Outputs**
- Daily nutrient summaries (sodium, potassium, sodium-to-potassium ratio, energy, saturated fat).
- A weekly nutrient summary.
- Dietary features that can later be passed to the trained classifier. The seven-day summary is an application-level extension for planned meals and is not seven-day NHANES training data.

### Planned later
- Food-medication interaction checking (Diet-Drug Interactions Database), shown as safety information for caregiver review.
- Integration with the shared backend and dashboard.

## Data
- NHANES 2017-March 2020 files are downloaded from the CDC website and are never committed to git.
- Raw, processed and external data folders are git-ignored.
- API keys (for example the USDA FoodData Central key) must be kept in a local `.env` file and never committed.

## Folder structure
```text
ai/component3-nutrition/
├── data/          # local data only (git-ignored contents)
├── notebooks/     # exploration and experiments, run in numeric order
├── models/        # trained models (large files are git-ignored)
├── src/           # reusable Python code
├── tests/         # tests for the code in src/
└── README.md
```

## How to run
Use Python 3.12. From the repository root:

```bash
source ai/venv/bin/activate
python -m pip install -r ai/requirements.txt
```

Select the `ai/venv` interpreter as the Jupyter kernel, then run the notebooks in numeric order.

## Status

### Implemented
- NHANES-based BP category modelling workflow and model-comparison results.
- Saved XGBoost model and feature metadata for the selected demographic + multi-day diet feature set.
- BP-associated category prediction module with input validation and class probabilities.
- Meal-plan nutrient aggregation with daily summaries and complete-plan totals.
- USDA FoodData Central integration, including nutrient normalization, reference-quantity handling, and supported unit conversions.
- Automated tests covering nutrient calculation, meal-plan resolution, model prediction, saved-model loading, and USDA integration.

### Verification
- Component 3 automated test suite: 99 tests passed in the latest run.
- Classifier performance is experimental. The model classifies BP-associated categories from the features used during training; it is not a clinical diagnosis or a validated predictor of future blood pressure.
- Planned meal summaries are not equivalent to observed NHANES dietary recalls. Directly passing planned-meal values to the classifier requires further validation.

### Remaining work
- Verify the end-to-end workflow and define safe boundaries between planned-meal summaries and classifier inputs.
- Develop and test the caregiver-facing interface and application integration, if required by the project plan.
- Document setup, configuration, and demonstration steps.