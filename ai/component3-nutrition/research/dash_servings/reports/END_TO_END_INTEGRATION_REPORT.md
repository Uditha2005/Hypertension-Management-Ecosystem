# Component 3 — Daily DASH Optimizer Integration Report

## Implemented
- Added `POST /dash/optimize-current-day`, called by the nutrition results UI after meal-plan analysis.
- The frontend submits each day's entered foods only when the selected quantity has a defensible gram basis.
- Backend maps food descriptions to supported DASH food-group leaders using a documented keyword map; unrecognized foods are reported rather than guessed.
- Converts gram quantities to dataset serving units using the source food-group metadata.
- Optimizes daily food-group servings against the supplied DASH aggregate nutrient constraint matrix.
- Returns before/after servings, material changes, mapped and unmapped foods, constraint diagnostics, and limitations.
- UI displays up to five largest group-level changes only when the solver reports a verified `optimal` solution. Warnings do not display changes as recommendations.
- Removed the obsolete live `/dash/optimize-daily-pattern` endpoint that used a weak demographic-to-observed-intake regression to generate a starting profile. Its research scripts, metrics, and model artifact remain documented for reproducibility but are not used by the live optimizer.
- Removed Python caches, pytest caches, compiled bytecode, and OS metadata from the archive.

## Test evidence
- Full Component 3 backend suite: **158 passed**.
- Common-food mapping and optimizer tests cover cooked rice, roasted chicken, spinach, orange juice, pancakes, and an unknown mixed dish.
- API tests check successful execution, unknown-food reporting, and invalid quantities.
- A local example with cooked rice, roasted chicken, pancakes, and orange juice returned an `optimal` status with zero reported normalized constraint violation.

## Important limitations
1. The live optimizer now includes an experimental trained Ridge behavioural prediction model. It predicts next-day observed food-group servings, not meal suitability or clinical benefit; the constrained optimizer remains a separate component.
2. The keyword food-group mapper is deliberately limited and may misclassify ambiguous food names. Unmatched entries are surfaced.
3. The source matrix and nutrient bounds represent aggregate daily food-group profiles. They are not validated clinical targets for a specific person or a single meal.
4. Optimized changes can be large and may not respect taste, affordability, cultural context, or individual clinical needs. The UI shows a maximum of five group changes and labels the output as research-only.
5. Backend tests passed. The React production build could not be run in this environment because frontend dependencies (`react-scripts` / `node_modules`) are not installed. Browser-level UI verification remains outstanding.
6. The trained behavioural model has limited predictive performance (held-out variance-weighted R² about 0.175) and must not be interpreted as clinical validation. This implementation does not claim that it reduces blood pressure or replaces advice from a registered dietitian or clinician.

## Reproduction
From the repository root:
```bash
python -m pytest -q
```
Start the API and frontend using the commands in the main README. A valid `USDA_FDC_API_KEY` remains required for live USDA search and nutrient calculation.
