# Annotation guide for personalized dietary suggestion ranking

## Purpose

This guide is for collecting reviewable labels for a research-only ranking experiment. It is not a clinical protocol and does not authorize a suggestion that conflicts with medicine information or professional advice.

## Unit of annotation

One row is one candidate suggestion for one participant's meal/day context. A context should contain enough information to judge relevance (recorded foods, quantities where available, known nutrient values, meal/day scope, stated preferences and any *confirmed* active ingredients). Do not use an image model's unconfirmed guess as a confirmed food or prescription fact.

## Suggested relevance scale

- **0 — Not appropriate / irrelevant:** does not fit the available context, relies on a false assumption, conflicts with a verified precaution, or cannot be supported by the recorded data.
- **1 — Low relevance:** potentially reasonable in general but weakly connected to this context or too vague to be actionable.
- **2 — Relevant:** fits the context and is supported by an identifiable dietary rationale, but is not the strongest candidate.
- **3 — High relevance:** specific, practical, supported by the available evidence and especially well matched to the person's stated context/preferences.

A reviewer should use the `review_status` field and add a note explaining any score of 0 or 3. Do not use 0 to mean "unknown"; leave the label blank and mark the row pending if there is insufficient information.

## Evidence and safety rules

1. Every candidate must have a stable `candidate_suggestion_id` and a `candidate_type`.
2. Record evidence source IDs/URLs in `evidence_source_ids`; a source must support the reason stated, not merely mention the food or medicine.
3. Drug–food precautions must come from verified product information or an appropriate curated interaction source. The ML model must not infer safety from correlations in dietary data.
4. An unresolved brand or OCR string is not an active ingredient. Mark the medication context unresolved and do not create a medicine-specific label.
5. If a candidate is ruled out by a verified safety check, set `eligible_after_safety_filter=false`; do not ask the ranker to decide whether to ignore the safety check.
6. `constraint_proxy_label` is for a separate proxy experiment only. It must not be copied into `expert_relevance_label`.
7. Reviewers should score candidate suggestions without seeing the model's predicted score where practical, reducing anchoring bias.
8. Record review date and reviewer role without storing unnecessary personal identifiers. Use pseudonymous participant IDs and follow applicable consent/privacy requirements.

## Evaluation recommendations

- Split train/validation/test by participant, never by individual candidate row alone.
- Keep all candidates from the same participant on one side of the split.
- Use NDCG@3 only for contexts with at least two independently labelled eligible candidates.
- Report the number of participants, contexts, labelled candidates, missing features, label distribution and evidence coverage alongside each metric.
- Compare against the transparent rule baseline. A model is not useful merely because training succeeds.
- Report medication-check false positives/false negatives separately from ranking metrics.
- Treat a small pilot as feasibility evidence, not clinical validation. A clinical outcome claim requires a separate prospective evaluation.

## Suggested review workflow

1. A developer generates candidate suggestions and attaches the reason and evidence.
2. A qualified nutrition reviewer checks food-group/nutrient relevance and meal/day scope.
3. A pharmacist or qualified medication reviewer checks medication-specific warnings where present.
4. Reviewers score independently where possible; resolve disagreements and preserve original scores.
5. Freeze the reviewed dataset version before model comparison and record its hash/row counts in the experiment manifest.
