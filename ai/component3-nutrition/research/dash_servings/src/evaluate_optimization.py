"""Reproduce regression comparison and evaluate the exact DASH projection on real holdout profiles."""
from pathlib import Path
import argparse, zipfile, tempfile, json, sys
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from dash_optimizer import load_problem, check_feasibility, normalized_bound_violation, optimize_servings

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-zip", required=True)
    ap.add_argument("--output", default="../results/reproduced")
    ap.add_argument("--profiles", type=int, default=100)
    args=ap.parse_args()
    out=Path(args.output); out.mkdir(parents=True, exist_ok=True)
    from train_compare_servings import load_source
    joined,codes=load_source(args.data_zip)
    features=["RIDAGEYR","RIAGENDR","hypertension_reported"]
    targets=[f"food_{c}" for c in codes]
    X=joined[features].astype(float); Y=joined[targets].astype(float)
    Xtr,Xte,Ytr,Yte=train_test_split(X,Y,test_size=.2,random_state=42)
    models={
        "DummyMedian": Pipeline([("imputer",SimpleImputer(strategy="median")),("model",MultiOutputRegressor(DummyRegressor(strategy="median")))]),
        "RandomForest": Pipeline([("imputer",SimpleImputer(strategy="median")),("model",RandomForestRegressor(n_estimators=180,min_samples_leaf=3,max_features=.8,random_state=42,n_jobs=-1))]),
        "ExtraTrees": Pipeline([("imputer",SimpleImputer(strategy="median")),("model",ExtraTreesRegressor(n_estimators=180,min_samples_leaf=3,max_features=.8,random_state=42,n_jobs=-1))]),
    }
    fitted={}; rows=[]
    for name, model in models.items():
        model.fit(Xtr,Ytr)
        pred=np.maximum(model.predict(Xte),0)
        rows.append({"model":name,"holdout_mae_servings_per_food_group":mean_absolute_error(Yte,pred),
                     "holdout_variance_weighted_r2":r2_score(Yte,pred,multioutput="variance_weighted"),
                     "train_participants":len(Xtr),"test_participants":len(Xte)})
        fitted[name]=model
    comparison=pd.DataFrame(rows).sort_values("holdout_mae_servings_per_food_group")
    comparison.to_csv(out/"preference_model_comparison.csv",index=False)
    selected_name=comparison.iloc[0]["model"]
    joblib.dump(fitted[selected_name],out/"selected_preference_model.joblib")
    pred=np.maximum(fitted[selected_name].predict(Xte),0)
    pd.DataFrame(pred,index=Yte.index,columns=targets).to_csv(out/"selected_model_holdout_predictions.csv",index_label="SEQN")

    # Evaluate exact constrained projection on a sample of real held-out dietary profiles.
    # These are real observed profiles, not generated training rows.
    coef_path=Path(__file__).resolve().parents[1]/"results/nutrient_coefficients.csv"
    bounds_path=Path(__file__).resolve().parents[1]/"results/dash_nutrient_bounds.csv"
    meta_path=Path(__file__).resolve().parents[1]/"results/food_group_metadata.csv"
    nutrient_names,codes2,A,lb,ub,scale=load_problem(coef_path,bounds_path,meta_path)
    feasibility=check_feasibility(A,lb,ub,len(codes2))
    if not feasibility["feasible"]:
        raise RuntimeError("Source constraints are infeasible under nonnegative servings: "+feasibility["message"])
    code_cols=[f"food_{c}" for c in codes2]
    # Align held-out observed target to coefficient order
    actual=Yte[code_cols].to_numpy(float)
    n=min(args.profiles,len(actual))
    records=[]; nutrient_rows=[]
    for i in range(n):
        x0=np.maximum(actual[i],0)
        before=A@x0
        before_sum,before_max=normalized_bound_violation(before,lb,ub)
        opt=optimize_servings(x0,coef_path,bounds_path,meta_path)
        after=np.array([opt["nutrients"][name] for name in nutrient_names],float)
        after_sum,after_max=normalized_bound_violation(after,lb,ub)
        dist=float(np.sqrt(np.sum(((np.array(list(opt["servings"].values()))-x0)/scale)**2)))
        records.append({"SEQN":int(Yte.index[i]),"solver_success":opt["success"],"solver_status":opt["status"],
                        "iterations":opt.get("iterations",-1),"violation_sum_before":before_sum,
                        "max_violation_before":before_max,"violation_sum_after":after_sum,
                        "max_violation_after":after_max,"scaled_preference_distance":dist,
                        "objective":opt.get("objective",np.nan)})
        for j,name in enumerate(nutrient_names):
            nutrient_rows.append({"SEQN":int(Yte.index[i]),"nutrient":name,"before":before[j],
                                  "after":after[j],"lower_bound":lb[j],"upper_bound":ub[j],
                                  "before_within_bounds":bool(lb[j]-1e-6<=before[j]<=ub[j]+1e-6),
                                  "after_within_bounds":bool(lb[j]-1e-6<=after[j]<=ub[j]+1e-6)})
    ev=pd.DataFrame(records); ev.to_csv(out/"optimizer_holdout_evaluation.csv",index=False)
    pd.DataFrame(nutrient_rows).to_csv(out/"optimizer_nutrient_detail.csv",index=False)
    summary={
        "participants_total":int(len(joined)),"train_participants":int(len(Xtr)),"test_participants":int(len(Xte)),
        "features":features,"target":"mean observed food-group servings across NHANES Day 1 and Day 2",
        "selected_regressor_by_holdout_MAE":selected_name,
        "model_comparison":comparison.to_dict(orient="records"),
        "optimizer_constraints_feasible":feasibility["feasible"],
        "optimizer_profiles_evaluated":int(n),
        "optimizer_success_rate":float(ev.solver_success.mean()),
        "mean_violation_sum_before":float(ev.violation_sum_before.mean()),
        "mean_violation_sum_after":float(ev.violation_sum_after.mean()),
        "median_violation_sum_before":float(ev.violation_sum_before.median()),
        "median_violation_sum_after":float(ev.violation_sum_after.median()),
        "profiles_all_constraints_satisfied_after":int((ev.max_violation_after<=1e-7).sum()),
        "mean_scaled_preference_distance":float(ev.scaled_preference_distance.mean()),
        "caution":"This optimizes aggregate daily food-group profiles against source-derived nutrient bounds; it is not meal suitability or clinical validation."
    }
    (out/"evaluation_summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
