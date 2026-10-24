# Medication-aware dietary suggestion ranking — research scaffold

## Status

The application currently uses an auditable rule-based suggestion baseline plus a conservative, optional medication-precaution screen. **A trained ranking model is not yet part of the live application.** This repository now includes a training/evaluation pipeline that deliberately refuses to train on missing or undersized labels.

## Application data flow

1. Component 3 identifies foods through the existing Gemini photo workflow or manual USDA search.
2. The user can edit the AI-suggested food names and portions. Photo suggestions are resolved through the same first-result USDA search behavior that existed before the temporary “Confirm USDA food record” UI was added; the USDA record and portion remain visible in the food entry for review.
3. Component 3 validates the quantity against the USDA record's actual nutrient reference basis and supported units before analysis.
4. The current rule service generates practical food-group/nutrient suggestions and conservative medication reminders from ingredients the user explicitly confirms in Component 3. Component 4 files and code are not modified or automatically connected.
5. The future ranker will score eligible candidate suggestions. It must never replace the verified interaction/safety layer.

## Training data

`training_examples_template.csv` describes one candidate suggestion per row. Features are numeric flags/scores for the food-group context, sodium context, medication precaution context, food-group fit, preference match and evidence strength. `candidate_type` is categorical.

- `expert_relevance_label`: independent reviewer score (recommended 0–3).
- `constraint_proxy_label`: rule-derived proxy score, not expert judgement.
- `label_source`: `expert` or `proxy`.
- `eligible_after_safety_filter`: candidates rejected by the safety/evidence filter must not be ranked for display.
- `participant_id`: pseudonymous ID used to keep participants separated across train/validation/test splits.

Do not populate expert labels from the same rules being evaluated. The included CSV is a blank schema, not training data.

## Training/evaluation

Install the Component 3 Python dependencies and provide a CSV with enough labelled examples. The script requires at least 30 eligible rows, 5 participants and 10 meal contexts and splits by participant to reduce leakage.

```bash
python ai/component3-nutrition/research/medication_aware_ranking/src_train_ranker.py \
  --input /path/to/reviewed_training_examples.csv \
  --output-dir ai/component3-nutrition/research/medication_aware_ranking/results
```

By default, only rows with `label_source=expert` and a valid `expert_relevance_label` are used. To run an explicitly exploratory proxy-label experiment, add `--allow-proxy-labels`; document those results as proxy-only and do not describe them as expert validated.

The script compares Ridge regression, Random Forest and Extra Trees; reports validation/test MAE, held-out NDCG@3 for contexts with at least two expert-labelled candidates, and a transparent rule-baseline NDCG. When expert-labelled validation contexts are available, selection prioritizes validation NDCG@3 and uses MAE as a tie-breaker; without expert labels, it falls back to MAE and explicitly marks the run proxy-only. The selected artifact is a research candidate only: neither metric establishes clinical utility. Review ranking metrics and expert assessment before integration. Do not deploy the saved artifact merely because training succeeds.

## Data-readiness audit

Run the audit against the blank template or a populated candidate CSV:

```bash
python ai/component3-nutrition/research/medication_aware_ranking/audit_training_data.py \
  --input ai/component3-nutrition/research/medication_aware_ranking/training_examples_template.csv \
  --output ai/component3-nutrition/research/medication_aware_ranking/results/data_readiness.json
```

The blank template is expected to report `not_ready`; the audit does not invent examples or labels. It reports eligible rows, expert/proxy label counts, participants, multi-candidate contexts and missing feature values.

## Medicine catalogue coverage audit

`medication_catalogue_coverage_template.csv` records the 22 medicine-folder labels shown in the user's catalogue screenshots. It is an audit worksheet, not a confirmed medication list. Several brand/spelling/strength labels are intentionally marked unresolved. A pharmacist or reliable package/prescription source must confirm the active ingredient before interaction matching. Fill official label URLs, database match counts, evidence quality and reviewer status only after checking the source. Do not interpret a blank interaction match as proof that no interaction exists.

## Source-linked interaction registry (partial)

`ai/component3-nutrition/src/medication_food_interactions.json` now stores selected, source-linked reminders based on official NHS patient guidance. The current entries cover specific triggers for ramipril, irbesartan, losartan, spironolactone, amlodipine, nifedipine, verapamil and clopidogrel. Rules trigger only when both a confirmed active ingredient and a relevant food/substance term are present. The catalogue label `Nitedipine` is deliberately not normalized to nifedipine automatically.

This registry is intentionally incomplete. It is not a replacement for DDID, official product information, or pharmacist review. A missing rule is not evidence that no interaction exists. The UI should only present the rule as a precaution to verify, never as a diagnosis or a complete interaction check.

The source links were reviewed for this implementation on 2026-10-23:

- Ramipril and potassium-containing salt substitutes: https://www.nhs.uk/medicines/ramipril/common-questions-about-ramipril/
- Irbesartan: https://www.nhs.uk/medicines/irbesartan/
- Losartan: https://www.nhs.uk/medicines/losartan/
- Spironolactone: https://www.nhs.uk/medicines/spironolactone/
- Amlodipine: https://www.nhs.uk/medicines/amlodipine/
- Nifedipine: https://www.nhs.uk/medicines/nifedipine/
- Verapamil: https://www.nhs.uk/medicines/verapamil/common-questions-about-verapamil/
- Clopidogrel: https://www.nhs.uk/medicines/clopidogrel/common-questions-about-clopidogrel/
- DDID downloadable interaction data: https://bddg.hznu.edu.cn/ddid/download/

Run the catalogue coverage audit:

```bash
python ai/component3-nutrition/research/medication_aware_ranking/audit_interaction_coverage.py
```

The generated report currently records 22 catalogue labels, 18 candidate ingredient labels, 4 unresolved labels and 9 local source-linked rules. Ten catalogue rows map to an ingredient with at least one local rule because multiple folder entries share ingredients. These counts describe only this small local registry; they are not total interaction coverage and do not indicate that the catalogue ingredients have been confirmed from patient prescriptions.

## Required next experiment

1. Audit DDID and official medicine information for active ingredients in the supported medicine catalogue.
2. Record source, active ingredient, food/substance, interaction type, evidence level, exact guidance and review date.
3. Build candidate suggestions from explicit dietary constraints and food-group context.
4. Have a qualified nutrition/medication reviewer label a representative subset where feasible.
5. Compare the transparent rules baseline, linear model and tree ranker using participant-grouped splits.
6. Report ranking quality, nutrition constraint violations and interaction-check false positives/false negatives separately.
7. Integrate only if the trained ranker meaningfully outperforms the baseline and passes independent review.

## Limitations

- The medication screen is deliberately narrow; it is not a complete drug–food interaction database.
- No prescription data is pulled automatically from Component 4. Users can manually enter confirmed active ingredients in Component 3; this is an interim research workflow.
- The training template contains no labelled examples, so no model is trained by this change.
- The prototype is not clinical decision support and does not replace official product information or advice from a pharmacist/clinician.

## DDID import and evidence review workflow

`DDID_REVIEW_WORKFLOW.md` documents a reproducible import-and-review process for the public DDID export. The export can be downloaded from https://bddg.hznu.edu.cn/ddid/download/ (the page lists a file named `Interaction Information.csv`). Run `audit_ddid_export.py --input /path/to/Interaction\ Information.csv` to profile the actual file schema and export medication-keyword review candidates. The script preserves source columns, labels candidates as unreviewed, and never writes runtime rules. It is designed to be run after the dataset is downloaded; the DDID export itself is not bundled in this repository, and no DDID rows are represented as reviewed here.

`ddid_review_log_template.csv` provides fields for record IDs, source version, food form, interaction category, references, reviewers, and decisions. Only reviewed, source-supported rules should be considered for the runtime registry.

The training template is still blank because this workspace does not contain independent reviewer judgements or participant-level examples. The workflow describes how to collect these without fabricating labels. A trained, expert-validated ranking model cannot honestly be completed until those labels are collected.


## Scope note: current ML direction

The current proposed direction is **ML-driven personalized nutrition actions**, not a standalone recommendation-ranking model. The legacy `src_train_ranker.py` and its training template are retained as research history and are not part of the active recommendation-action pipeline. The active four-candidate experiment is `../../train_compare_recommendation_models.py`, under `research/personalized_recommendations/`. Do not claim the new model is trained: the current recommendation-action template contains zero labelled examples.
