"""Fixed ex-ante weights on variance forecasts; no fitting on evaluation losses."""
import json
import numpy as np
import pandas as pd
from src.evaluation.walkforward import FORECAST_COLS

KEY=["symbol","horizon_days","window","origin_date"]

def combine_forecasts(frames,components,name="combo_econ",weights=None):
    if len(components)<2 or len(set(components))!=len(components):raise ValueError("Need distinct component models")
    if weights is None:weights={model:1/len(components) for model in components}
    if set(weights)!=set(components) or not np.isfinite(list(weights.values())).all() or min(weights.values())<=0 or not np.isclose(sum(weights.values()),1):
        raise ValueError("Weights must be positive fixed weights summing to one")
    selected={model:frames[model].copy() for model in components}
    reference=selected[components[0]]
    hashes=set(reference["dataset_sha256"]);protocols=set(reference["protocol_sha256"])
    if len(hashes)!=1 or len(protocols)!=1:raise ValueError("Ambiguous forecast provenance")
    # Full outer keys retain failures and missing components as explicit unavailable rows.
    keys=pd.concat([frame[KEY] for frame in selected.values()],ignore_index=True).drop_duplicates().sort_values(KEY)
    output=keys.copy();component_frames=[]
    for model,frame in selected.items():
        if not frame["model"].eq(model).all():raise ValueError("Component model identity mismatch")
        if frame.duplicated(KEY).any():raise ValueError("Duplicate component key")
        if set(frame["dataset_sha256"])!=hashes or set(frame["protocol_sha256"])!=protocols:raise ValueError("Component provenance mismatch")
        valid=frame.loc[frame["status"].eq("ok"),"rv_forecast_pct2"]
        if not np.isfinite(valid).all() or valid.le(0).any():raise ValueError("Invalid successful component variance")
        component_frames.append(keys.merge(frame,on=KEY,how="left",validate="one_to_one").reset_index(drop=True))
    output=output.reset_index(drop=True)
    for col in ["target_start","target_date","forecast_available_at","refit_origin","train_start"]:
        values=pd.concat([frame[col] for frame in component_frames],axis=1)
        if values.nunique(axis=1,dropna=True).gt(1).any():raise ValueError(f"Component calendar mismatch: {col}")
        metadata=values.iloc[:,0].copy()
        for i in range(1,values.shape[1]):metadata=metadata.combine_first(values.iloc[:,i])
        output[col]=metadata  # coalesce identical metadata at this origin only
    complete=pd.concat([frame["status"].eq("ok") for frame in component_frames],axis=1).all(axis=1)
    total=np.zeros(len(output));mean=np.zeros(len(output))
    for model,frame in zip(components,component_frames):
        total+=weights[model]*frame["rv_forecast_pct2"].to_numpy()
        mean+=weights[model]*frame.get("mean_forecast_pct",pd.Series(0.,index=frame.index)).to_numpy()
    output["model"]=name;output["rv_forecast_pct2"]=np.where(complete,total,np.nan)
    output["volatility_forecast_pct"]=np.sqrt(output["rv_forecast_pct2"])
    for col in ["train_end","train_feature_end"]:
        output[col]=pd.concat([frame[col] for frame in component_frames],axis=1).max(axis=1)
    output["n_train"]=pd.concat([frame["n_train"] for frame in component_frames],axis=1).min(axis=1).fillna(0).astype(int)
    output["training_kind"]="combination";output["status"]=np.where(complete,"ok","component_unavailable")
    output["protocol_sha256"]=next(iter(protocols));output["dataset_sha256"]=next(iter(hashes))
    output["mean_forecast_pct"]=np.where(complete,mean,np.nan);output["nu"]=np.nan
    output["student_t_scale_pct"]=np.nan;output["innovation_distribution"]="combination_requires_separate_risk_method"
    output["combination_components"]=json.dumps(components);output["combination_weights"]=json.dumps(weights,sort_keys=True)
    output["error_message"]=np.where(complete,"","At least one required component forecast is unavailable")
    return output[FORECAST_COLS+[col for col in output if col not in FORECAST_COLS]]
