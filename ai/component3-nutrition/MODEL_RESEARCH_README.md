# Component 3 model research workflow

## Selected application model

The application now loads `models/selected_daily_intake.joblib`, produced by
`src/run_final_training_experiment.py`. The selected candidate is chosen by
five-fold cross-validation macro-F1 **among models using demographic + Day 1
dietary features**, because this input shape can represent the average daily
intake entered in the application, including a one-day plan.

The training target remains the NHANES BP-associated category:
Normal, Elevated, Stage 1, or Stage 2. It is **not** a label for whether an
individual meal is suitable. The application therefore displays the model's
BP-associated category estimate separately from the nutrient-reference
assessment.

## Reproduce the controlled experiment

From the repository root:

```bash
source ai/venv/bin/activate
python ai/component3-nutrition/src/run_final_training_experiment.py
python -m pytest ai/component3-nutrition/tests -q
```

The script:
- restricts the research cohort to adults aged 60–80, matching the elderly-care scope;
- uses participants with complete Day 1 and Day 2 nutrient features for a matched comparison;
- compares demographic-only, demographic + Day 1, and demographic + two-day-mean feature sets;
- compares Logistic Regression, Random Forest, Extra Trees and RBF SVM;
- uses the same stratified development/holdout split and five-fold CV for all candidates;
- selects the deployed candidate using CV macro-F1 among the Day 1 feature set only;
- evaluates the selected candidate on the existing holdout and records that this holdout has been examined in earlier project experiments;
- saves the pipeline, training metadata, comparison table, confusion matrix and report.

Outputs are written under `results/final_training/`. The selected model and metadata
are written under `models/selected_daily_intake.joblib` and
`models/selected_daily_intake.metadata.json`.

## Application behaviour

- The caregiver enters foods, quantities and resident characteristics.
- USDA nutrient values are aggregated by date.
- The classifier uses the mean daily totals over the selected dates and returns an exploratory BP-associated category estimate.
- A separate dietary assessment checks entered daily sodium against a general adult reference of 2,300 mg/day.
- A local feature-sensitivity explanation replaces one input at a time with its development-partition median and reports how the model score changes. This is an approximate model-behaviour explanation, not a causal explanation.
- The UI makes clear that the model output is not a diagnosis, meal-suitability label, calibrated clinical risk, or prediction of future BP.

## Research limitations

NHANES provides observed 24-hour dietary recalls paired with measured BP. It does not provide direct labels for planned-meal suitability. Consequently, the current ML target remains BP-associated category classification. The nutrient-reference assessment is kept separate; it must not be presented as if the ML model were trained to predict it.

The selected holdout has prior exposure in project experiments, so test metrics are exploratory rather than pristine independent confirmation. Results must be reported as measured; do not promise a target accuracy or claim clinical validity. The sodium reference is general adult guidance and only applies to foods entered for the selected day; it is not a personalised prescription.

## Historical experiments

Earlier scripts, models and results are retained as research history. Do not delete or use a historical artifact as the active application model unless the configuration and metadata are updated intentionally.
