"""Feasibility-checked DASH nutrient-constrained projection.

This is a convex quadratic projection/optimization prototype, not a trained meal-suitability
classifier. Inputs are daily food-group servings. Source-derived nutrient constraints must not
be applied directly to a single meal.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize, Bounds, LinearConstraint

def load_problem(coefficient_csv, bounds_csv, scale_csv):
    coeff = pd.read_csv(coefficient_csv, index_col=0)
    bounds = pd.read_csv(bounds_csv).set_index("nutrient").loc[coeff.index]
    metadata = pd.read_csv(scale_csv).set_index("food_code")
    codes = [int(c) for c in coeff.columns]
    metadata = metadata.loc[codes]
    A = coeff.to_numpy(dtype=float)
    lb = bounds["lower_bound"].to_numpy(dtype=float)
    ub = bounds["upper_bound"].to_numpy(dtype=float)
    scale = np.maximum(metadata["scale_for_optimization"].to_numpy(dtype=float), 0.25)
    if not (A.shape[0] == len(lb) == len(ub)):
        raise ValueError("Coefficient and nutrient-bound dimensions do not match.")
    if not np.isfinite(A).all() or not np.isfinite(lb).all() or not np.isfinite(ub).all():
        raise ValueError("Constraint matrix/bounds contain non-finite values.")
    if np.any(lb > ub):
        raise ValueError("At least one nutrient lower bound exceeds its upper bound.")
    return coeff.index.tolist(), codes, A, lb, ub, scale

def check_feasibility(A, lb, ub, n_variables, variable_bounds=None):
    bounds = variable_bounds if variable_bounds is not None else [(0, None)] * n_variables
    result = linprog(c=np.zeros(n_variables), A_ub=np.vstack([A, -A]),
                     b_ub=np.concatenate([ub, -lb]), bounds=bounds,
                     method="highs")
    return {"feasible": bool(result.success), "status": int(result.status),
            "message": str(result.message), "feasible_point": result.x if result.success else None}

def normalized_bound_violation(nutrients, lb, ub):
    denom = np.maximum(np.maximum(np.abs(lb), np.abs(ub)), 1.0)
    violation = (np.maximum(lb - nutrients, 0.0) + np.maximum(nutrients - ub, 0.0)) / denom
    return float(np.sum(violation)), float(np.max(violation, initial=0.0))

def optimize_servings(preferred, coefficient_csv, bounds_csv, scale_csv,
                      maxiter=2500, gtol=1e-8, xtol=1e-10, allowed_codes=None):
    nutrient_names, codes, A, lb, ub, scale = load_problem(coefficient_csv, bounds_csv, scale_csv)
    x0 = np.asarray(preferred, dtype=float).reshape(-1)
    if len(x0) != len(codes):
        raise ValueError(f"Expected {len(codes)} serving values, got {len(x0)}.")
    if not np.isfinite(x0).all():
        raise ValueError("Preferred serving profile contains non-finite values.")
    x0 = np.maximum(x0, 0.0)
    allowed = set(codes if allowed_codes is None else (int(code) for code in allowed_codes))
    variable_bounds = [(0.0, None) if code in allowed else (0.0, 0.0) for code in codes]
    feasibility = check_feasibility(A, lb, ub, len(codes), variable_bounds)
    if not feasibility["feasible"]:
        nutrients = A @ x0
        v_sum, v_max = normalized_bound_violation(nutrients, lb, ub)
        return {"success": False, "status": "infeasible_constraints",
                "message": feasibility["message"], "servings": dict(zip(codes, x0.tolist())),
                "nutrients": dict(zip(nutrient_names, nutrients.tolist())),
                "normalized_violation_sum": v_sum, "max_normalized_bound_violation": v_max,
                "preference_distance_scaled": 0.0}

    # Drop only mathematically redundant zero-coefficient rows, e.g. alcohol=0 when every
    # representative group has zero alcohol. Keep them in output checks below.
    active = np.any(np.abs(A) > 1e-14, axis=1)
    A_active, lb_active, ub_active = A[active], lb[active], ub[active]
    def objective(x):
        return float(np.sum(((x - x0) / scale) ** 2))
    def gradient(x):
        return 2.0 * (x - x0) / (scale ** 2)
    def hessian(x):
        return np.diag(2.0 / (scale ** 2))

    # Trust-constr handles the linear constraints directly; unlike a large penalty it cannot
    # trade away constraint satisfaction for a lower objective.
    res = minimize(
        objective, np.maximum(feasibility["feasible_point"], 0.0),
        jac=gradient, hess=hessian, method="trust-constr",
        bounds=Bounds(np.zeros(len(codes)), np.array([np.inf if code in allowed else 0.0 for code in codes])) ,
        constraints=[LinearConstraint(A_active, lb_active, ub_active)],
        options={"maxiter": maxiter, "gtol": gtol, "xtol": xtol, "verbose": 0},
    )
    x = np.maximum(res.x, 0.0)
    nutrients = A @ x
    v_sum, v_max = normalized_bound_violation(nutrients, lb, ub)
    # A solver termination flag alone is not enough: verify the original, unscaled constraints.
    success = bool(res.success and v_max <= 1e-7)
    return {
        "success": success, "status": "optimal" if success else "solver_or_residual_warning",
        "solver_message": str(res.message), "iterations": int(getattr(res, "nit", -1)),
        "objective": objective(x), "normalized_violation_sum": v_sum,
        "max_normalized_bound_violation": v_max,
        "preference_distance_scaled": float(np.sqrt(objective(x))),
        "servings": dict(zip(codes, x.tolist())),
        "nutrients": dict(zip(nutrient_names, nutrients.tolist())),
    }
