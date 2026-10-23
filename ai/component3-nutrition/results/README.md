# New-scope experiment results

Status: **NOT RUN — genuine labelled meal-suitability data are not present in the supplied project.**

No metrics or selected model are fabricated. `comparisons/candidate_model_status.csv` lists candidates with blank metrics and explicitly marks them as not evaluated. After a valid dataset is added, `src/train_compare_models.py` writes:
- `comparisons/model_comparison.csv`
- `comparisons/best_model_confusion_matrix.csv`
- `comparisons/best_model_classification_report.json`
- model artifact and metadata under `models/`

Until those outputs exist, the API reports `training_pending`.
