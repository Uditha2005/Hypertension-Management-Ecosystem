# Component 3 — DASH-Informed Personalized Meal Assessment and Diet Optimization for Hypertension

This module is part of the Hypertension Management Ecosystem. It replaces the earlier BP-category classifier workflow with the agreed meal-assessment and daily diet-optimization flow. The root React entry file `frontend/web/src/index.js` is intentionally unchanged.

## Application workflow

1. Enter age, optional BMI, and relevant dietary requirements.
2. Search foods using USDA FoodData Central, select foods, and enter quantities and units.
3. Calculate available sodium, potassium, energy, saturated-fat, and sodium-to-potassium totals.
4. Assess each meal using transparent dietary-reference context and explain nutrient concerns.
5. If the user confirms the entered foods represent the complete day's intake, the main analysis flow calls the saved ML classifier to estimate the daily nutrient-reference alignment proxy. The model only runs when its required nutrient features are available.
6. Use the daily DASH optimizer to explore daily food-group patterns under the dataset's daily nutrient constraints.

Meal-level assessment remains reference-based. The main analysis flow now optionally invokes the trained classifier for a complete day's intake, returning a daily reference-alignment proxy category with a clear limitation. The classifier is not a meal-suitability model. Daily nutrient references are context and are not meal-level clinical limits. Unknown nutrient values are not treated as zero.

## ML training and research

The project contains two separate ML research tasks using the bundled real dietary dataset:

### A. Daily nutrient-reference alignment proxy classification

```bash
python ai/component3-nutrition/src/train_proxy_alignment_models.py
```

The script uses real NHANES Day 1 nutrient records joined with demographics. It creates an explicitly rule-derived *daily nutrient-reference alignment proxy* target, then compares Logistic Regression, Random Forest, Extra Trees, and HistGradientBoosting. The variables defining the proxy label are excluded from the predictor set. Participants are grouped across splits. The script saves the selected fitted model and comparison/held-out evaluation artifacts.

This is weak supervision: the model learns a proxy derived from documented rules. These labels are **not** expert-labelled ground truth, meal-level suitability labels, or clinical outcomes.

### B. Daily food-group preference regression and DASH optimization

```bash
python ai/component3-nutrition/research/dash_servings/src/train_compare_servings.py
python ai/component3-nutrition/research/dash_servings/src/evaluate_optimization.py
```

This task predicts observed daily food-group servings using participant-level dietary records and then projects a profile against documented daily DASH nutrient constraints. It is not a meal-suitability classifier. The bundled results include validation comparison, held-out evaluation, and optimizer evaluation.

## Setup

From the repository root:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
python -m pip install -r ai/component3-nutrition/requirements.txt
cp .env.example .env
# Set USDA_FDC_API_KEY in .env for live USDA food search.
npm --prefix frontend/web ci
```

Run the API and UI in separate terminals:

```bash
npm run dev:nutrition-api
npm run dev:web
```

API docs: http://127.0.0.1:8000/docs

Build the frontend:

```bash
npm run build:web
```

Run tests:

```bash
python -m pytest ai/component3-nutrition/tests ai/component3-nutrition/research/dash_servings/tests -q
```

## Important interpretation limits

- The application does not diagnose hypertension or prescribe an individual diet.
- A meal's nutrients cover only foods entered and may be incomplete if USDA nutrient values are missing.
- Daily DASH constraints apply to daily food-group patterns, not single meals.
- The proxy classification task learns rule-derived daily reference alignment; it does not establish real-world meal suitability.
- Performance is reported as observed and may be weak; no clinical validity is implied.
- Live USDA lookup requires a valid USDA FoodData Central API key.
