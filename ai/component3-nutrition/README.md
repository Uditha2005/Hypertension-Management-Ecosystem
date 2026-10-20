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

### Scope exclusions
- Food-medication interaction checking is excluded from the selected PP1 scope.
- The caregiver-facing interface belongs to a later phase.

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

## API (Phase 4)

The FastAPI layer wraps the existing USDA adapter, meal-plan service, classifier-feature builder, and predictor. It does not duplicate nutrient calculations or select a USDA search result automatically.

### Endpoints

- `GET /health` — process health check; does not call USDA or load the model.
- `GET /foods/search?query=oats&limit=10` — returns USDA food candidates. A caller must choose an explicit `fdc_id` for a planned entry.
- `POST /meal-plans/analyze` — resolves planned foods, returns daily and complete-plan nutrient summaries, constructs classifier features from explicitly selected dates, and returns the experimental prediction.
- `GET /docs` — interactive OpenAPI documentation while the server is running.

### Configure and run

Install dependencies from the repository root:

```bash
source ai/venv/bin/activate
python -m pip install -r ai/requirements.txt
```

Set the USDA key in the shell environment (do not commit it):

```bash
export USDA_FDC_API_KEY="your_usda_api_key"
```

Start the API from the repository root:

```bash
python -m uvicorn api:app --app-dir ai/component3-nutrition/src --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. The health endpoint works without the USDA key, but food search and meal-plan analysis require it. The classifier model artifact must also be present for a real prediction.

### Example meal-plan request

```json
{
  "entries": [
    {"day": "2026-10-12", "fdc_id": 12345, "quantity": 150, "unit": "g"},
    {"day": "2026-10-13", "fdc_id": 67890, "quantity": 1, "unit": "serving"}
  ],
  "selected_days": ["2026-10-12", "2026-10-13"],
  "age": 58,
  "sex_female": 1,
  "bmi": 26.4
}
```

The IDs above are examples only; use IDs returned by USDA food search. Supported quantity units are `g`, `kg`, and `serving`, subject to the reference basis of the selected USDA record. The API rejects unsupported conversions and unknown required nutrients rather than assuming they are zero.

The response contains `daily_nutrients`, `complete_plan_total`, `classifier_features`, and `prediction`. Classifier features are calculated only from `selected_days`; the complete-plan total is for nutrition reporting and is not used as a daily mean.

### Run tests

From the repository root:

```bash
ai/venv/bin/python -m pytest ai/component3-nutrition/tests/test_api.py -q
ai/venv/bin/python -m pytest ai/component3-nutrition/tests -q
```

API tests use fake USDA records and a stubbed prediction function; they do not make real network requests or load the trained model.

## Status

### Implemented
- NHANES-based BP category modelling workflow and model-comparison results.
- Saved XGBoost model and feature metadata for the selected demographic + multi-day diet feature set.
- BP-associated category prediction module with input validation and class probabilities.
- Meal-plan nutrient aggregation with daily summaries and complete-plan totals.
- USDA FoodData Central integration, including nutrient normalization, reference-quantity handling, and supported unit conversions.
- Automated tests covering nutrient calculation, meal-plan resolution, model prediction, saved-model loading, USDA integration, and API endpoints.
- FastAPI endpoints for health checks, USDA food search, and meal-plan analysis.

### Verification
- Before the API phase, the Component 3 automated test suite passed 143 tests.
- The API-focused tests pass in the isolated implementation review; rerun the full suite in the project virtual environment after applying the files.
- Classifier performance is experimental. The model classifies BP-associated categories from the features used during training; it is not a clinical diagnosis or a validated predictor of future blood pressure.
- Planned meal summaries are not equivalent to observed NHANES dietary recalls. Directly passing planned-meal values to the classifier requires further validation.

### Remaining work
- Verify the end-to-end workflow and define safe boundaries between planned-meal summaries and classifier inputs.
- Develop and test the caregiver-facing interface and application integration, if required by the project plan.
- Document setup, configuration, and demonstration steps.