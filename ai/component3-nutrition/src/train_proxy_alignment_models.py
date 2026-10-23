"""Train a clearly labelled weak-supervision experiment on real NHANES day-1 records.

The target is a DAILY nutrient-reference alignment proxy derived from published
reference criteria; it is not expert-labelled meal suitability or clinical truth.
Inputs deliberately exclude sodium, saturated fat, and energy, which define the
proxy label, to avoid direct target leakage. Results must be described as proxy
label prediction only.
"""
from __future__ import annotations
import json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, cross_validate
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix, precision_score, recall_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier

BASE = Path(__file__).resolve().parents[1]
ARCHIVE = BASE / 'research' / 'dash_servings' / 'data_source' / 'Dietary-Behavior-Dataset-master.zip'
OUT = BASE / 'results' / 'proxy_alignment'
MODEL_DIR = BASE / 'models'
NUTRIENT_FILE = 'Dietary-Behavior-Dataset-master/Data/NHANES Total Nutrients Day 1.csv'
DEMO_FILE = 'Dietary-Behavior-Dataset-master/Data/NHANES Demographics.csv'

# Predictors do not include the three variables used to create the proxy label.
NUMERIC = ['DR1TPOTA','DR1TFIBE','DR1TPROT','DR1TCARB','DR1TCALC','DR1TMAGN','DR1TVC','RIDAGEYR']
CATEGORICAL = ['RIAGENDR']
TARGET = 'alignment_proxy_label'

def load_real_nhanes() -> pd.DataFrame:
    if not ARCHIVE.exists():
        raise SystemExit(f'Cannot find the bundled real-data archive: {ARCHIVE}')
    with zipfile.ZipFile(ARCHIVE) as z:
        nutrients = pd.read_csv(z.open(NUTRIENT_FILE), low_memory=False)
        demos = pd.read_csv(z.open(DEMO_FILE), low_memory=False)
    df = nutrients.merge(demos[['SEQN','RIDAGEYR','RIAGENDR']], on='SEQN', how='inner', validate='one_to_one')
    # Whitespace and special NHANES missing encodings must not be interpreted as zero.
    required = ['DR1TSODI','DR1TSFAT','DR1TKCAL'] + NUMERIC + CATEGORICAL + ['SEQN']
    for col in required:
        df[col] = pd.to_numeric(df[col].replace(r'^\s*$', np.nan, regex=True), errors='coerce')
    df = df.dropna(subset=['SEQN','DR1TSODI','DR1TSFAT','DR1TKCAL'] + NUMERIC + CATEGORICAL).copy()
    df = df[(df['DR1TKCAL'] > 0) & (df['DR1TSODI'] >= 0) & (df['DR1TSFAT'] >= 0)]
    satfat_share = (df['DR1TSFAT'] * 9.0) / df['DR1TKCAL']
    # Explicitly weak, rule-derived proxy, not a ground-truth meal-suitability label.
    passes = (df['DR1TSODI'] <= 2300.0) & (satfat_share <= 0.06)
    df[TARGET] = np.where(passes, 'reference_aligned_proxy', 'needs_review_proxy')
    df['participant_group'] = df['SEQN'].astype(str)
    return df

def main():
    df = load_real_nhanes()
    X = df[NUMERIC + CATEGORICAL].copy()
    y = df[TARGET].astype(str)
    groups = df['participant_group']
    # One row per participant and split grouping by participant for reproducibility.
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    g_train = groups.iloc[train_idx]
    min_class_groups = int(df.iloc[train_idx].groupby(TARGET)['participant_group'].nunique().min())
    folds = min(5, min_class_groups)
    if folds < 2:
        raise SystemExit('Not enough participants in each proxy class for grouped cross-validation.')
    pre = ColumnTransformer([
        ('num', Pipeline([('imputer', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), NUMERIC),
        ('cat', Pipeline([('imputer', SimpleImputer(strategy='most_frequent'))]), CATEGORICAL),
    ], remainder='drop')
    candidates = {
        'LogisticRegression': Pipeline([('features', pre), ('model', LogisticRegression(max_iter=2500, class_weight='balanced'))]),
        'RandomForest': Pipeline([('features', pre), ('model', RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight='balanced', random_state=42, n_jobs=-1))]),
        'ExtraTrees': Pipeline([('features', pre), ('model', ExtraTreesClassifier(n_estimators=300, min_samples_leaf=3, class_weight='balanced', random_state=42, n_jobs=-1))]),
        'HistGradientBoosting': Pipeline([('features', pre), ('model', HistGradientBoostingClassifier(max_iter=150, random_state=42))]),
    }
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=42)
    rows, fitted = [], {}
    for name, pipe in candidates.items():
        scores = cross_validate(pipe, X_train, y_train, groups=g_train,
            cv=cv.split(X_train, y_train, g_train),
            scoring={'macro_f1':'f1_macro','accuracy':'accuracy','weighted_f1':'f1_weighted'}, n_jobs=-1)
        pipe.fit(X_train, y_train)
        pred = pipe.predict(X_test)
        rows.append({'model':name,'cv_macro_f1_mean':float(scores['test_macro_f1'].mean()),
                     'cv_macro_f1_std':float(scores['test_macro_f1'].std()),
                     'cv_accuracy_mean':float(scores['test_accuracy'].mean()),
                     'heldout_accuracy':float(accuracy_score(y_test,pred)),
                     'heldout_macro_f1':float(f1_score(y_test,pred,average='macro')),
                     'heldout_weighted_f1':float(f1_score(y_test,pred,average='weighted')),
                     'heldout_macro_precision':float(precision_score(y_test,pred,average='macro',zero_division=0)),
                     'heldout_macro_recall':float(recall_score(y_test,pred,average='macro',zero_division=0))})
        fitted[name] = (pipe, pred)
    results = pd.DataFrame(rows).sort_values(['cv_macro_f1_mean','cv_accuracy_mean'], ascending=False)
    OUT.mkdir(parents=True, exist_ok=True); MODEL_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUT/'four_model_comparison.csv', index=False)
    best_name = str(results.iloc[0]['model']); best, pred = fitted[best_name]
    labels = sorted(y.unique())
    pd.DataFrame(confusion_matrix(y_test,pred,labels=labels), index=labels, columns=labels).to_csv(OUT/'heldout_confusion_matrix.csv')
    (OUT/'heldout_classification_report.json').write_text(json.dumps(classification_report(y_test,pred,output_dict=True,zero_division=0),indent=2))
    joblib.dump(best, MODEL_DIR/'daily_reference_alignment_proxy.joblib')
    manifest = {
      'experiment':'weak_supervision_daily_nutrient_reference_alignment',
      'target':TARGET,
      'label_definition': 'reference_aligned_proxy iff Day 1 sodium <= 2300 mg AND saturated fat energy share <= 6%; otherwise needs_review_proxy',
      'label_status':'rule-derived proxy labels; NOT expert ground truth, NOT meal-suitability labels, NOT clinical validation',
      'source':'NHANES Day 1 total nutrient intake and demographics files bundled in Dietary-Behavior-Dataset-master.zip',
      'rows_after_required_value_filter':int(len(df)), 'train_rows':int(len(train_idx)), 'heldout_rows':int(len(test_idx)),
      'unique_participants':int(df['SEQN'].nunique()), 'class_counts':{str(k):int(v) for k,v in y.value_counts().items()},
      'features':NUMERIC+CATEGORICAL, 'excluded_label_defining_features':['DR1TSODI','DR1TSFAT','DR1TKCAL'],
      'split':'GroupShuffleSplit by SEQN, test_size=0.20, random_state=42',
      'selection':'highest grouped-CV macro-F1; held-out set used only for final evaluation',
      'selected_model':best_name,
      'references_context':{'sodium_mg_per_day':2300,'saturated_fat_energy_share':0.06},
      'caution':'A model trained on labels derived from rules approximates those rules using other nutrient/demographic features. It does not establish independently validated suitability.'}
    (OUT/'experiment_manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'README.md').write_text('''# Daily nutrient-reference alignment proxy experiment\n\nThis experiment makes model training possible using real NHANES Day 1 dietary records, without fabricating observations. The target is explicitly **rule-derived weak supervision**: a daily record is `reference_aligned_proxy` if sodium is <= 2300 mg/day and saturated-fat energy share is <= 6%; otherwise it is `needs_review_proxy`.\n\nThese are proxy labels generated from documented thresholds, **not** expert-reviewed labels, ground truth, clinical outcomes, or meal-level suitability. Sodium, saturated fat, and energy are excluded from model predictors because they define the proxy label. Four candidate classifiers are compared using participant-grouped cross-validation; a held-out participant set is used for final metrics.\n\nThe experiment is useful as a methodological/weak-supervision component, but its results must not be described as clinically validated meal-suitability prediction. The app's transparent nutrient assessment remains the primary meal-level feature.\n\nRun from the repository root:\n```bash\npython ai/component3-nutrition/src/train_proxy_alignment_models.py\n```\n''')
    print(results.to_string(index=False))
    print(f'\nSelected by grouped CV macro-F1: {best_name}')
    print(f'Rows: {len(df)}; train={len(train_idx)}; heldout={len(test_idx)}; labels={y.value_counts().to_dict()}')

if __name__ == '__main__': main()
