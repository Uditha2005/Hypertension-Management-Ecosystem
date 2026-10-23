import json
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
def test_four_candidate_comparison_and_holdout_exist():
    out=HERE/'results'/'training'
    assert (out/'four_model_validation_comparison.csv').exists()
    assert (out/'heldout_test_summary.csv').exists()
    import pandas as pd
    models=set(pd.read_csv(out/'four_model_validation_comparison.csv')['model'])
    assert models == {'DummyMedian','RandomForest','ExtraTrees','HistGradientBoosting'}
    assert (out/'selected_food_group_preference_model.joblib').exists()
def test_manifest_scope_is_not_meal_suitability():
    manifest=json.loads((HERE/'results'/'training'/'training_manifest.json').read_text())
    assert 'not meal suitability' in manifest['scope_warning'].lower()
