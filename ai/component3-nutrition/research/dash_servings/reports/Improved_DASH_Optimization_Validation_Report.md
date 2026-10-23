# Improved DASH Optimization: Implementation and Validation Report

**Date:** 22 October 2026
**Data:** user-supplied `Dietary-Behavior-Dataset-master.zip`, containing NHANES-derived dietary records and source-provided DASH optimization constraints.
**Synthetic data:** none. No artificial training rows or suitability labels were generated.

## What was changed

The prior optimizer used a penalty-based objective and returned a non-convergence warning on the sampled holdout profiles. The improved implementation now:

1. Checks linear constraint feasibility with `scipy.optimize.linprog` before optimization.
2. Solves a nonnegative, weighted least-squares projection with `scipy.optimize.minimize(method="trust-constr")` and explicit linear constraints.
3. Removes only zero-coefficient constraint rows from the solver (for example, a zero-alcohol row where every representative food has zero alcohol), while still validating all original nutrient constraints in the final output.
4. Independently calculates each result's nutrient values and normalized bound violations.
5. Reports solver status and preference distance instead of silently treating a penalty reduction as a successful solution.

This is a constrained projection prototype using the source dataset's supplied aggregate daily nutrient bounds. It is not a faithful reproduction of the paper's full inverse-learning algorithm, and the bounds are for aggregate daily diet profiles, not single meals.

## Data split and regression comparison

- Participants after joins and eligibility filtering: **4,402**
- Training participants: **3,521**
- Held-out participants: **881**
- Features: age (`RIDAGEYR`), sex (`RIAGENDR`), self-reported hypertension (`BPQ020` mapped to yes/no).
- Target: average observed food-group servings across Day 1 and Day 2, for 50 food groups.
- Split: 80/20 random participant-level split (`random_state=42`); each participant contributes one row, so participant IDs do not cross the split.

| Candidate | Holdout MAE (servings / food group) | Variance-weighted R² |
|---|---:|---:|
| DummyMedian | 0.3497 | -0.1015 |\n| RandomForest | 0.4314 | -0.0433 |\n| ExtraTrees | 0.4318 | -0.0456 |\n
The selected regression candidate by lowest holdout MAE remains **DummyMedian**, the median baseline. Random Forest and Extra Trees performed worse. Negative variance-weighted R² indicates the candidates did not predict food-group serving patterns well enough to justify a more complex demographic-to-intake model. This is a negative finding and should be reported honestly.

## Constrained optimizer validation

The source-provided nutrient constraints were feasible under nonnegative food-group servings (`linprog` feasibility check: **True**).

The optimizer was evaluated on **100 real held-out participant dietary profiles**. These profiles are used only for evaluation; no synthetic data were generated.

| Metric | Result |
|---|---:|
| Solver success rate | 100.0% |
| Mean normalized bound-violation sum before optimization | 21.045127 |
| Mean normalized bound-violation sum after optimization | 1.338e-11 |
| Median normalized bound-violation sum before | 5.663083 |
| Median normalized bound-violation sum after | 0.000e+00 |
| Profiles meeting all supplied nutrient bounds after optimization | 100/100 |
| Mean scaled distance from original profile | 9.6195 |

The optimizer achieved numerical feasibility for all 100 tested profiles. However, the average scaled preference distance (**9.62**) indicates it can make substantial changes to the original intake pattern. This is a trade-off, not proof that recommendations are acceptable or healthy. Constraint satisfaction is an internal mathematical metric, not a clinical outcome.

## What this does and does not establish

**Established:** the supplied nutrient constraint system is feasible under the implemented nonnegative formulation, and the updated solver reached constraint-satisfying results on 100 real held-out profiles.

**Not established:**
- personalized meal suitability;
- clinical effectiveness or reduced blood pressure;
- that the optimized profile is acceptable to a user or dietitian;
- superior performance to the source paper's original inverse-learning algorithm;
- validated individual-level daily DASH prescriptions.

The coefficient matrix and nutrient bounds are inherited from the uploaded repository. Their derivation, units, and interpretation must be checked against the source paper and a nutrition-domain reviewer before clinical-facing use. The source bounds should not be applied directly to a single meal.

## Recommended next step

Do not promote the weak demographic-to-intake regression as the primary model. Use the constrained optimizer as a **research prototype/baseline**, add explicit preference and food-group constraints where justified by the source formulation, and compare against the original paper's inverse-learning method after verifying its mathematical objective. The application should calculate meal nutrients and provide transparent reference-based feedback; optimization should be described as a daily diet-pattern research feature until validated.

## Reproduction

Install `numpy`, `pandas`, `scikit-learn`, `scipy`, and `joblib`. Extract `data_source/Dietary-Behavior-Dataset-master.zip` and run:

```bash
python src/evaluate_optimization.py \
  --data-zip data_source/Dietary-Behavior-Dataset-master.zip \
  --output results/reproduced --profiles 100
```

Run tests from the package root:

```bash
python -m pytest tests -q
```

Source dataset citation: Ahmadi, F., Ganjkhanloo, F., & Ghobadi, K. (2020). *An Open-Source Dataset on Dietary Behaviors and DASH Eating Plan Optimization Constraints*. arXiv:2010.07531. Respect source terms and cite it in research outputs.
