# Component 3 model research workflow

This workflow preserves the Component 3 application code and separates model training, comparison, and tuning into explicit stages.

## Environment

Use Python 3.12 and the repository virtual environment. From the repository root:

```bash
source ai/venv/bin/activate
python --version
python -m pip install -r ai/component3-nutrition/requirements.txt
```

If the component has its own environment instead, activate that environment consistently; do not mix interpreters.

## Workflow

Run each algorithm separately from the repository root:

```bash
python ai/component3-nutrition/src/train_logistic_regression.py
python ai/component3-nutrition/src/train_random_forest.py
python ai/component3-nutrition/src/train_svm.py
python ai/component3-nutrition/src/train_xgboost.py
```

Each script evaluates the same three feature sets:
- demographics only;
- demographics + Day 1 diet;
- demographics + available multi-day recall means.

Each run uses the same deterministic, stratified 80/20 participant-level split (`random_state=42`) and stratified five-fold CV on the 80% training partition. Preprocessing that learns parameters (such as standard scaling) is inside the model pipeline and is fit within each fold. The 20% test partition is not used for model or hyperparameter selection.

Compare saved results and select the candidate by mean CV macro-F1:

```bash
python ai/component3-nutrition/src/compare_models.py
```

Then tune the selected candidate using the training partition only and evaluate it on the held-out test partition:

```bash
python ai/component3-nutrition/src/tune_best_model.py
```

Run tests:

```bash
python -m pytest ai/component3-nutrition/tests -q
```

## Outputs

- `results/model_research/<model>_cv.csv`: per-feature-set cross-validation means, standard deviations, and fold scores.
- `results/model_research/<model>_test.csv`: held-out test metrics for all adults and the age-60+ subset.
- `results/model_research/all_models_cv_results.csv`: combined, ranked CV results.
- `results/model_research/all_models_test_results.csv`: combined test metrics, reported only after candidate selection.
- `results/model_research/selected_candidate.json`: selection rule and selected baseline configuration.
- `models/research_candidates/`: research candidate estimators; not used by the production prediction API.
- `models/final/tuned_research_candidate.joblib` and metadata: tuned research candidate, not automatically promoted to the app model.

## Why Python files and a notebook?

Python scripts are the canonical executable training pipeline because they are repeatable, testable, and can be run from the terminal/CI. `notebooks/01_nhanes_merge_and_labels.ipynb` remains the data-construction and label-provenance notebook. `notebooks/02_model_comparison.ipynb` is retained as a results/reporting notebook: run the scripts first, then use the notebook to review the saved results and plots. It no longer contains a separate implementation of the training loop.

## Research safeguards and limitations

- `systolic_avg` and `diastolic_avg` are not predictor features; BP readings define the target categories only.
- This dataset is one row per participant; the split is participant-level and stratified, not external or temporal validation.
- NHANES dietary inputs are 24-hour recalls, not seven-day planned meals. Planned-meal application inputs are not identical to observed recall features.
- Macro-F1 is the primary selection metric because the classes are imbalanced. Accuracy, macro precision/recall, weighted F1, per-class reports, confusion matrices, and age-60+ results are also saved.
- The candidate is experimental, not a diagnosis or clinically validated prediction.
- First-stage CV selects among models and feature sets; the second-stage tuning CV score is exploratory because the winning configuration was chosen in a preceding comparison. The held-out test set remains separate from both training and tuning.


## File inventory

- `src/model_research.py`: shared data validation, split, estimator factory, CV/test evaluation, artifact writing.
- `src/train_logistic_regression.py`: Logistic Regression run entry point.
- `src/train_random_forest.py`: Random Forest run entry point.
- `src/train_svm.py`: Linear SVM run entry point.
- `src/train_xgboost.py`: XGBoost run entry point.
- `src/compare_models.py`: reads the four saved CV/test outputs, ranks candidates using CV macro-F1, and writes the selected-candidate record; it does not retrain models.
- `src/tune_best_model.py`: second-stage training-partition-only hyperparameter search for the selected candidate and one held-out test evaluation.
- `notebooks/02_model_comparison.ipynb`: report notebook that visualizes saved results; it no longer contains a separate model-training implementation.
- `tests/test_model_research.py`: regression tests for label mapping, leakage exclusions, dataset validity, split reproducibility, and estimator creation.
