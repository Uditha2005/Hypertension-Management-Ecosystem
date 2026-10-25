# Component 3 — DASH-Informed Personalized Meal Assessment and Diet Optimization for Hypertension

This module is part of the Hypertension Management Ecosystem. It replaces the earlier BP-category classifier workflow with the agreed meal-assessment and daily diet-optimization flow. The root React entry file `frontend/web/src/index.js` is intentionally unchanged.

## Application workflow

1. Enter age, optional BMI, and relevant dietary requirements.
2. Search foods using USDA FoodData Central, select foods, and enter quantities and units.
3. Calculate available sodium, potassium, energy, saturated-fat, and sodium-to-potassium totals.
4. Assess each meal using transparent dietary-reference context and explain nutrient concerns.
5. An earlier daily nutrient-reference alignment proxy classifier was removed from the packaged model artifacts because it was not used by the main UI. Its training script and evaluation records remain for research traceability.
6. Run the integrated daily DASH optimizer on each day's entered foods. The API maps recognizable food descriptions to the dataset's food-group leaders, converts confirmed gram quantities to group servings, and projects the profile against source-provided daily nutrient constraints. Unknown foods are listed as unmapped rather than guessed.

Meal-level assessment is reference-based. No trained ML model currently powers the live DASH recommendation section. The DASH optimizer is a constrained mathematical optimization engine, not a trained ML model. Daily nutrient references are context and are not meal-level clinical limits. Unknown nutrient values are not treated as zero.

## ML training and research

The project contains two separate ML research tasks using the bundled real dietary dataset:

### A. Daily nutrient-reference alignment proxy classification

```bash
python ai/component3-nutrition/src/train_proxy_alignment_models.py
```

The script uses real NHANES Day 1 nutrient records joined with demographics. It creates an explicitly rule-derived *daily nutrient-reference alignment proxy* target, then compares Logistic Regression, Random Forest, Extra Trees, and HistGradientBoosting. The variables defining the proxy label are excluded from the predictor set. Participants are grouped across splits. The script saves the selected fitted model and comparison/held-out evaluation artifacts.

This is weak supervision: the model learns a proxy derived from documented rules. These labels are **not** expert-labelled ground truth, meal-level suitability labels, or clinical outcomes.

### B. Daily food-group preference regression and DASH optimization (research only)

```bash
python ai/component3-nutrition/research/dash_servings/src/train_compare_servings.py
python ai/component3-nutrition/research/dash_servings/src/evaluate_optimization.py
```

The demographic-to-observed-serving regression was evaluated and performed poorly: the selected DummyMedian baseline has held-out MAE around 0.345 servings per food group and negative variance-weighted R². It is retained only as a research result and is not used by the live recommendation flow.

The live `/dash/optimize-current-day` endpoint instead starts from the user's actual entered food descriptions and gram quantities, maps them to food-group serving estimates, and applies the source constraint matrix. It is a constrained optimization prototype, not a trained ML model or a faithful reproduction of the paper's full inverse-learning algorithm. Food mapping is keyword-based and may leave foods unmatched; results must be reviewed and must not be described as clinically validated.

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
python -m pytest -q
```

## Important interpretation limits

- The application does not diagnose hypertension or prescribe an individual diet.
- A meal's nutrients cover only foods entered and may be incomplete if USDA nutrient values are missing.
- Daily DASH constraints apply to daily food-group patterns, not single meals. The UI runs the optimizer per selected day, but the food-group mapping and source constraint transfer remain research-prototype approximations.
- The proxy classification task learns rule-derived daily reference alignment; it does not establish real-world meal suitability.
- Performance is reported as observed and may be weak; no clinical validity is implied.
- Live USDA lookup requires a valid USDA FoodData Central API key.


## Photo-based meal entry

The API exposes `POST /foods/identify-image`. When the FoodSeg103 checkpoint and PyTorch/torchvision are available, the endpoint lazily loads the trained FCN-ResNet-50, caches it, and uses MPS when available (otherwise CUDA or CPU). The default checkpoint is `research/food_segmentation/results/full_data_experiment/fcn_resnet50_seed42/fcn_resnet50/best_model.pth`; set `FOODSEG103_CHECKPOINT` to override it. The checkpoint is not copied into a second model directory. Install compatible `torch` and `torchvision` packages in the backend environment to enable local inference.

Local segmentation returns FoodSeg103 class IDs/names, original-resolution pixel area and area fraction, and a transparent segmentation overlay. It does not estimate grams or return calibrated confidence. The web review requires users to edit/remove predictions, select a USDA FoodData Central record, and enter a portion before a food can be added for nutrient calculation. Pixel area is not a weight estimate.

If the checkpoint or inference dependencies are unavailable, configure `GEMINI_API_KEY` in the API process environment (optionally set `GEMINI_VISION_MODEL`, default `gemini-2.5-flash`) for the existing Gemini fallback. Gemini still returns approximate portion estimates; users must review those and choose a USDA record before calculation. Health reports the checkpoint and lazy inference status. Both image-recognition paths can miss hidden ingredients, cooking oil, salt, sauces, and foods outside the model's label set. FoodSeg103 is experimental and not a clinically validated food-recognition system.

Start the API from this directory:

```bash
python -m uvicorn src.api:app --reload --port 8000
```

Start the web app from `frontend/web` in a second terminal:

```bash
npm start
```

The web client defaults to `http://127.0.0.1:8000`; set `REACT_APP_NUTRITION_API_URL` before starting it if the API runs elsewhere.


## Medication-aware suggestion-ranking research (in progress)

The live “Suggestions for this meal” cards are currently generated by transparent rules, not by a trained ranking model. See `research/medication_aware_ranking/README.md` for the candidate-ranking experiment, training schema, data-readiness audit and medication-catalogue coverage worksheet. Run the data audit with:

```bash
python ai/component3-nutrition/research/medication_aware_ranking/audit_training_data.py \
  --input ai/component3-nutrition/research/medication_aware_ranking/training_examples_template.csv \
  --output ai/component3-nutrition/research/medication_aware_ranking/results/data_readiness.json
```

The included template intentionally has no labels, so the audit correctly reports `not_ready`. The training script refuses to invent labels and must not be used to claim expert validation. Medication names typed in Component 3 are an interim prototype input only; Component 4 is not automatically connected.


## Model-artifact cleanup (2026-10-24)

Unused saved model binaries were removed from this distribution; experiment scripts, manifests, and evaluation metrics remain:
- Daily nutrient-reference alignment proxy (`daily_reference_alignment_proxy.joblib`): removed; not connected to the main UI.
- Selected food-group serving regression artifact (`selected_food_group_preference_model.joblib`): removed; not connected to the live recommendation workflow. The recorded selection was the DummyMedian baseline, and held-out performance was weak.

Do not describe the live DASH optimizer as ML. A trained model must be intentionally integrated and verified before making that claim.

## Dietary Behavior Dataset suitability assessment

The supplied `Dietary-Behavior-Dataset-master.zip` contains real NHANES dietary observations, demographics and blood-pressure/diabetes questionnaire data, USDA food codes/serving-size information, and matrices/constraints for DASH diet optimization. Its README describes inverse learning to infer constrained linear optimization problems from observed dietary patterns.

This dataset is suitable for reproducing or extending constrained DASH optimization / inverse-learning research, and for experiments predicting observed food-group servings from participant features. However, observed intake is not a label for a good recommendation. The dataset does not directly provide expert-labelled pairs of (current meal, correct recommended alternative), so it is not a ready-made supervised meal-recommendation dataset.

Recommended next step: reproduce the published inverse-learning method using the supplied matrices and observed patterns, then evaluate constraint feasibility and whether the resulting changes are nutritionally and behaviourally reasonable. Keep the learned component and optimizer conceptually separate, and describe any model as experimental until validated.

Dataset citation: Ahmadi, F., Ganjkhanloo, F., & Ghobadi, K. (2020). *An Open-Source Dataset on Dietary Behaviors and DASH Eating Plan Optimization Constraints*. arXiv:2010.07531. Check the dataset's stated research-only/non-commercial terms before reuse or redistribution.


## DASH ML integration status (2026-10-24)

The current daily DASH recommendation endpoint now loads the trained `Ridge` multi-output model at `research/dash_servings/models/dash_next_day_preference_ridge.joblib`. It predicts observed next-day food-group servings from the mapped current-day serving profile. A 30% predicted / 70% current-profile blend becomes the optimizer's preference target; the existing constrained optimizer remains active. Model comparison and held-out metrics are documented in `research/dash_servings/README.md` and `research/dash_servings/results/new_ml_training/`.

This is an experimental behavioural prediction model, not a meal-healthiness classifier or clinically validated recommendation model.


## Simplified prototype storage and profile handling

Component 3 no longer connects to PostgreSQL or any external database. Meal history and optional feedback are stored as local JSON files for development only. The saved profile feature and `/profile` endpoints have been removed. Users enter assessment details in the form each time; these details are used for that request and are not loaded from a saved profile.

Historical experiment note: previous daily alignment, food-goal suitability, and serving-prediction model experiments were removed from active code/results. The current DASH Ridge model and DASH optimizer are retained.

## Experimental multi-food image segmentation comparison

The training experiment is available at `research/food_segmentation/`. The full-data FCN-ResNet-50 checkpoint is connected to `POST /foods/identify-image` when it and the optional PyTorch/torchvision dependencies are available; the endpoint falls back to Gemini when configured. The web review requires explicit food, USDA-record, and portion confirmation. This is experimental ingredient segmentation, not a clinically validated food-recognition or portion-estimation system. See the research folder README for model comparisons, metrics, and limitations.
