"""Four-candidate, real-data regression benchmark for observed food-group servings.
Target is average observed servings per food group across NHANES diet days 1 and 2.
This is not a meal-suitability target. Selection uses validation MAE; test set is held out.
"""
from pathlib import Path
import argparse, json, zipfile, shutil, tempfile, time
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, r2_score

HERE=Path(__file__).resolve().parent
PARAMS=HERE.parent/'data_source'/'Optimization Model Parameters'
DEFAULT_ZIP=HERE.parent/'data_source'/'Dietary-Behavior-Dataset-master.zip'

def load_source(data_zip):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(data_zip) as z: z.extractall(td)
        root=Path(td)/'Dietary-Behavior-Dataset-master'
        leaders=pd.read_csv(root/'Optimization Model Parameters/Food Group Leaders with Serving Sizes.csv')
        leaders['Food Code']=pd.to_numeric(leaders['Food Code'],errors='coerce')
        leaders=leaders.dropna(subset=['Food Code']).drop_duplicates('Food Code')
        leaders['Food Code']=leaders['Food Code'].astype(int)
        codes=leaders['Food Code'].tolist()
        serving=dict(zip(codes,pd.to_numeric(leaders['Serving (g)'],errors='coerce')))
        demo=pd.read_csv(root/'Data/NHANES Demographics.csv',low_memory=False).replace(r'^\s*$',np.nan,regex=True)
        for c in ['SEQN','RIDAGEYR','RIAGENDR']: demo[c]=pd.to_numeric(demo[c],errors='coerce')
        demo=demo.drop_duplicates('SEQN')
        bp=pd.read_csv(root/'Data/NHANES Blood Pressure Quesstionnaire.csv',low_memory=False).replace(r'^\s*$',np.nan,regex=True)
        bp['SEQN']=pd.to_numeric(bp.SEQN,errors='coerce')
        bp=bp.sort_values('SEQN').groupby('SEQN',as_index=False).agg({'BPQ020':lambda s:s.dropna().iloc[0] if len(s.dropna()) else np.nan})
        bp['hypertension_reported']=pd.to_numeric(bp.BPQ020,errors='coerce').map({1:1,2:0})
        def day(d):
            df=pd.read_csv(root/f'Data/NHANES Individual Food Consumption Day {d} (Reduced).csv',low_memory=False).replace(r'^\s*$',np.nan,regex=True)
            df['SEQN']=pd.to_numeric(df.SEQN,errors='coerce')
            df['grp']=(pd.to_numeric(df[f'DR{d}IFDCD'],errors='coerce')//1000000).astype('Int64')
            df['grams']=pd.to_numeric(df[f'DR{d}IGRMS'],errors='coerce')
            df=df[df.grp.isin(codes)].dropna(subset=['SEQN','grp','grams']).copy()
            df['grp']=df.grp.astype(int); df['servings']=df.apply(lambda r:r.grams/serving[r.grp],axis=1)
            df=df.replace([np.inf,-np.inf],np.nan).dropna(subset=['servings'])
            w=df.pivot_table(index='SEQN',columns='grp',values='servings',aggfunc='sum',fill_value=0).reindex(columns=codes,fill_value=0)
            w.columns=[f'food_{c}' for c in w.columns]; return w
        w1,w2=day(1),day(2); both=sorted(set(w1.index)&set(w2.index))
        y=(w1.loc[both]+w2.loc[both])/2; y.index.name='SEQN'; y=y.clip(lower=0)
        joined=demo[['SEQN','RIDAGEYR','RIAGENDR']].merge(bp[['SEQN','hypertension_reported']],on='SEQN',how='left').set_index('SEQN').join(y,how='inner')
        joined=joined[(joined.RIDAGEYR>=18)&joined.RIAGENDR.notna()&joined.hypertension_reported.notna()]
        return joined,codes

def metric(y, p):
    return {'mae_servings_per_food_group':float(mean_absolute_error(y,p)),
            'variance_weighted_r2':float(r2_score(y,p,multioutput='variance_weighted'))}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data-zip',type=Path,default=DEFAULT_ZIP)
    ap.add_argument('--output',type=Path,default=HERE.parent/'results')
    args=ap.parse_args(); out=args.output; out.mkdir(parents=True,exist_ok=True)
    df,codes=load_source(args.data_zip)
    features=['RIDAGEYR','RIAGENDR','hypertension_reported']; targets=[f'food_{c}' for c in codes]
    X=df[features].astype(float); Y=df[targets].astype(float)
    # Split participant-level rows into train/validation/test, without reusing test for selection.
    X_tv,X_test,Y_tv,Y_test=train_test_split(X,Y,test_size=.15,random_state=42)
    X_train,X_val,Y_train,Y_val=train_test_split(X_tv,Y_tv,test_size=.1764705882,random_state=42) # 70/15/15
    models={
      'DummyMedian':Pipeline([('imputer',SimpleImputer(strategy='median')),('model',MultiOutputRegressor(DummyRegressor(strategy='median')))]),
      'RandomForest':Pipeline([('imputer',SimpleImputer(strategy='median')),('model',RandomForestRegressor(n_estimators=120,min_samples_leaf=3,max_features=.8,random_state=42,n_jobs=-1))]),
      'ExtraTrees':Pipeline([('imputer',SimpleImputer(strategy='median')),('model',ExtraTreesRegressor(n_estimators=120,min_samples_leaf=3,max_features=.8,random_state=42,n_jobs=-1))]),
      'HistGradientBoosting':Pipeline([('imputer',SimpleImputer(strategy='median')),('model',MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=80,max_leaf_nodes=15,l2_regularization=1.0,random_state=42)))])
    }
    rows=[]; fitted={}
    for name,model in models.items():
        t=time.time(); model.fit(X_train,Y_train)
        pred=np.maximum(model.predict(X_val),0); m=metric(Y_val,pred)
        rows.append({'model':name,'validation_mae_servings_per_food_group':m['mae_servings_per_food_group'],
                     'validation_variance_weighted_r2':m['variance_weighted_r2'],'selection_metric':'validation_mae_servings_per_food_group',
                     'fit_seconds':round(time.time()-t,2)})
        fitted[name]=model
    comp=pd.DataFrame(rows).sort_values('validation_mae_servings_per_food_group')
    selected=comp.iloc[0]['model']
    # Refit chosen candidate on train+validation; evaluate once on untouched test.
    final=fitted[selected]; final.fit(X_tv,Y_tv)
    test_pred=np.maximum(final.predict(X_test),0); test_metrics=metric(Y_test,test_pred)
    joblib.dump(final,out/'selected_food_group_preference_model.joblib')
    comp.to_csv(out/'four_model_validation_comparison.csv',index=False)
    pd.DataFrame([{'selected_model':selected,**test_metrics,'test_participants':int(len(X_test)),
                   'validation_participants':int(len(X_val)),'training_participants':int(len(X_train)),
                   'eligible_participants':int(len(df)),'target':'average observed servings per food group across NHANES Day 1 and Day 2',
                   'not_a_meal_suitability_classifier':True}]).to_csv(out/'heldout_test_summary.csv',index=False)
    testpred=pd.DataFrame(test_pred,index=Y_test.index,columns=targets); testpred.index.name='SEQN'; testpred.to_csv(out/'heldout_test_predictions.csv')
    (out/'training_manifest.json').write_text(json.dumps({'dataset_zip':args.data_zip.name,'feature_columns':features,'target_columns':targets,
      'split':'70/15/15 train/validation/test, random_state=42; one row per participant after source join',
      'selection':'lowest validation MAE; held-out test used only after selection','selected_model':selected,
      'eligible_participants':len(df),'train':len(X_train),'validation':len(X_val),'test':len(X_test),
      'target_definition':'average observed daily servings per food group across dietary Day 1 and Day 2',
      'scope_warning':'This target is observed dietary behaviour, not meal suitability, clinical outcome, or causal preference.'},indent=2))
    print(comp.to_string(index=False)); print('Selected:',selected); print('Held-out test:',test_metrics)
if __name__=='__main__': main()
