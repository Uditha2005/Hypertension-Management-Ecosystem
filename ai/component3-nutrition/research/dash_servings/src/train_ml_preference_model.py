"""Train and compare ML models predicting NHANES Day 2 food-group servings from Day 1.

This is a behavioural continuity model used as a preference prior for the DASH optimizer.
It is NOT a meal-suitability classifier and not clinical decision support.
"""
from __future__ import annotations
import argparse, json, tempfile, zipfile, time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.metrics import mean_absolute_error, r2_score

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
DEFAULT_ZIP = RESEARCH / "data_source" / "Dietary-Behavior-Dataset-master.zip"

def load_paired_days(zip_path):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zip_path) as z: z.extractall(td)
        root = Path(td) / "Dietary-Behavior-Dataset-master"
        leaders = pd.read_csv(root / "Optimization Model Parameters/Food Group Leaders with Serving Sizes.csv")
        leaders["Food Code"] = pd.to_numeric(leaders["Food Code"], errors="coerce")
        leaders = leaders.dropna(subset=["Food Code"]).drop_duplicates("Food Code")
        leaders["Food Code"] = leaders["Food Code"].astype(int)
        codes = leaders["Food Code"].tolist()
        serving = dict(zip(codes, pd.to_numeric(leaders["Serving (g)"], errors="coerce")))
        def day(d):
            df = pd.read_csv(root / f"Data/NHANES Individual Food Consumption Day {d} (Reduced).csv", low_memory=False)
            df["SEQN"] = pd.to_numeric(df["SEQN"], errors="coerce")
            df["grp"] = (pd.to_numeric(df[f"DR{d}IFDCD"], errors="coerce") // 1000000).astype("Int64")
            df["grams"] = pd.to_numeric(df[f"DR{d}IGRMS"], errors="coerce")
            df = df[df.grp.isin(codes)].dropna(subset=["SEQN","grp","grams"]).copy()
            df["grp"] = df["grp"].astype(int)
            df["servings"] = [r.grams / serving[r.grp] if pd.notna(serving.get(r.grp)) and serving[r.grp] > 0 else np.nan for r in df.itertuples()]
            df = df.replace([np.inf,-np.inf], np.nan).dropna(subset=["servings"])
            w = df.pivot_table(index="SEQN", columns="grp", values="servings", aggfunc="sum", fill_value=0).reindex(columns=codes, fill_value=0)
            w.columns = [f"food_{c}" for c in w.columns]
            return w
        x, y = day(1), day(2)
        ids = sorted(set(x.index) & set(y.index))
        return x.reindex(ids).fillna(0), y.reindex(ids).fillna(0).clip(lower=0), codes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-zip", type=Path, default=DEFAULT_ZIP)
    ap.add_argument("--output-dir", type=Path, default=RESEARCH / "results/new_ml_training")
    ap.add_argument("--model-dir", type=Path, default=RESEARCH / "models")
    args = ap.parse_args()
    X, Y, codes = load_paired_days(args.data_zip)
    Xtv, Xtest, Ytv, Ytest = train_test_split(X, Y, test_size=.15, random_state=42)
    Xtrain, Xval, Ytrain, Yval = train_test_split(Xtv, Ytv, test_size=.1764705882, random_state=42)
    models = {
      "Ridge": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), MultiOutputRegressor(Ridge(alpha=10.0))),
      "RandomForest": make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(n_estimators=80,min_samples_leaf=3,max_features=.8,random_state=42,n_jobs=-1)),
      "ExtraTrees": make_pipeline(SimpleImputer(strategy="median"), ExtraTreesRegressor(n_estimators=80,min_samples_leaf=3,max_features=.8,random_state=42,n_jobs=-1)),
    }
    rows = []
    for name, model in models.items():
        start=time.time(); model.fit(Xtrain,Ytrain); pred=np.maximum(model.predict(Xval),0)
        rows.append({"model":name,"validation_mae_servings_per_food_group":float(mean_absolute_error(Yval,pred)),
                     "validation_variance_weighted_r2":float(r2_score(Yval,pred,multioutput="variance_weighted")),
                     "fit_seconds":round(time.time()-start,2)})
    # Pre-registered selection rule: highest validation variance-weighted R2 among actual ML candidates.
    selected_name = max(rows, key=lambda r:r["validation_variance_weighted_r2"])["model"]
    selected = models[selected_name]
    test_pred=np.maximum(selected.predict(Xtest),0)
    summary={"task":"Predict Day 2 observed food-group servings from Day 1 observed food-group servings",
      "dataset":"Dietary Behavior Dataset; paired NHANES Day 1 and Day 2 individual food-consumption records",
      "participants":int(len(X)),"food_group_outputs":len(codes),"split":"70/15/15 participant-level train/validation/test; random_state=42",
      "selection_rule":"Highest validation variance-weighted R2 among Ridge, RandomForest, ExtraTrees; held-out test used only after selection",
      "selected_model":selected_name,
      "validation":{"mae_servings_per_food_group":next(r["validation_mae_servings_per_food_group"] for r in rows if r["model"]==selected_name),
                    "variance_weighted_r2":next(r["validation_variance_weighted_r2"] for r in rows if r["model"]==selected_name)},
      "heldout_test":{"mae_servings_per_food_group":float(mean_absolute_error(Ytest,test_pred)),
                      "variance_weighted_r2":float(r2_score(Ytest,test_pred,multioutput="variance_weighted"))},
      "caution":"Predicts observed behaviour, not healthiness or clinical outcomes. Research prototype only."}
    # Refit chosen model on train+validation; test set remains untouched.
    selected.fit(Xtv,Ytv)
    args.output_dir.mkdir(parents=True,exist_ok=True); args.model_dir.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output_dir/"model_comparison_validation.csv",index=False)
    (args.output_dir/"training_summary.json").write_text(json.dumps(summary,indent=2))
    joblib.dump({"model":selected,"feature_columns":list(X.columns),"target_columns":list(Y.columns),"blend_weight":.30,
      "target_definition":summary["task"],"dataset":summary["dataset"],"selected_model":selected_name},
      args.model_dir/"dash_next_day_preference_ridge.joblib")
    print(json.dumps(summary,indent=2))
if __name__ == "__main__": main()
