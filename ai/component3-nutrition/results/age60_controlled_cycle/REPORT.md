# Controlled Component 3 Training Cycle — Adults Aged 60+

## Decision

**Preferred research candidate:** `ExtraTreesClassifier` with balanced class weights, selected using mean five-fold macro-F1 on the development partition. It is saved separately as `models/research_candidates/age60_extra_trees_balanced.joblib` and is **not connected to the production prediction service**. The existing production model was not overwritten.

## Dataset and protocol

- Source: `data/processed/rebuilt/nhanes_bp_diet_rebuilt.csv`
- Eligible complete two-day records, age 60+: **2,241**
- Stratified development partition: **1,792** records
- Reserved holdout: **449** records; **not scored, fitted on, or used for selection in this cycle**
- Features: age, sex, BMI, two-day mean sodium, potassium, energy, saturated fat, and sodium-to-potassium ratio
- Split seed: 2026; five-fold stratified CV seed: 42
- All candidates use identical CV folds. Missing numeric features are imputed within each training fold.

## Candidate comparison

| Candidate | Mean CV macro-F1 | Fold SD | Pooled OOF macro-F1 | Pooled OOF accuracy |
|---|---:|---:|---:|---:|
| Extra Trees, balanced | **0.3116** | 0.0190 | **0.3125** | 0.3298 |
| Logistic regression, balanced | 0.2945 | 0.0277 | 0.2955 | 0.3209 |
| Random Forest, balanced subsample | 0.2768 | 0.0245 | 0.2777 | 0.3214 |
| Histogram gradient boosting, balanced sample weights | 0.2759 | 0.0158 | 0.2759 | 0.2980 |

### Selected candidate: category-level out-of-fold metrics

| Category | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Normal | 463 | 0.3365 | 0.3780 | 0.3561 |
| Elevated | 320 | 0.1903 | 0.2219 | 0.2049 |
| Stage 1 | 378 | 0.2578 | 0.2619 | 0.2598 |
| Stage 2 | 631 | 0.4777 | 0.3899 | 0.4293 |

## Interpretation

Extra Trees balanced has the best mean CV macro-F1 of the four candidates, but performance remains modest. Elevated remains the weakest class, and the selected candidate does **not** establish adequate clinical performance. Compared with the prior age-60+ `target_115` experiment (mean macro-F1 about 0.2922), this controlled balanced Extra Trees candidate scores about 0.3116 under this cycle's configuration; because configurations differ, treat this as a promising comparison, not a statistically significant gain.

## Artifact and reproducibility

- Model: `models/research_candidates/age60_extra_trees_balanced.joblib`
- Metadata: `models/research_candidates/age60_extra_trees_balanced.metadata.json`
- Training script: `src/train_age60_candidate.py`
- Experiment script: `src/run_age60_controlled_cycle.py`
- Full fold results: `folds.csv`
- Category results: `per_category.csv`
- Confusion matrix in long format: `confusion_matrix_long.csv`
- Audit: `audit.json`
- Test suite after adding these files: **182 passed**

The candidate was fitted only on the 1,792-row development partition after CV selection. The 449-row holdout remains reserved. Note that this dataset and holdout were examined in earlier work, so the holdout is not pristine external confirmation.

## Limitations

NHANES dietary recalls represent observed intake, not planned meal inputs. This classifier predicts BP-associated categories from demographic and dietary features; it does not prove diet causes BP category, diagnose hypertension, or forecast future BP. Before considering production integration, validate planned-meal feature distribution and evaluate on genuinely independent data if available.
