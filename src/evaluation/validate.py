"""Validate forecast identity, dates, information cutoffs and provenance before aggregation."""
import numpy as np
import pandas as pd
from src.features.schema import y_col
from src.evaluation.walkforward import FORECAST_COLS,refit_origin
from src.utils.config import protocol_hash

def truth_table(dataset,horizons):
    parts=[]
    for h in horizons:
        t=dataset[["symbol","origin_date","regime",y_col(h),f"target_segment_h{h}"]].rename(
            columns={y_col(h):"y_true",f"target_segment_h{h}":"target_segment"})
        t["horizon_days"]=h;parts.append(t)
    return pd.concat(parts,ignore_index=True)

def validate_forecasts(fc,dataset,config,dataset_hash=None,name="forecast"):
    missing=set(FORECAST_COLS+["protocol_sha256","dataset_sha256"])-set(fc.columns)
    if missing: return [f"{name}: missing columns {sorted(missing)}"]
    errors=[]
    key=["symbol","model","horizon_days","window","origin_date"]
    if fc.duplicated(key).any(): errors.append("Duplicate forecast keys")
    if fc.empty: return ["Empty forecast file"]
    if not fc["horizon_days"].isin([1,7]).all() or not fc["window"].isin(["rolling","expanding"]).all(): errors.append("Unsupported task")
    if not fc["status"].isin(["ok","missing_features","insufficient_train","fit_failed","forecast_failed","component_unavailable"]).all(): errors.append("Invalid status")
    dates={c:pd.to_datetime(fc[c],utc=True,errors="coerce") for c in ["origin_date","target_start","target_date","forecast_available_at","refit_origin","train_start","train_end","train_feature_end"]}
    origin=dates["origin_date"];ok=fc["status"].eq("ok")
    if not dates["target_start"].eq(origin+pd.Timedelta(days=1)).all(): errors.append("Wrong target start")
    if not dates["target_date"].eq(origin+pd.to_timedelta(fc["horizon_days"],unit="D")).all(): errors.append("Wrong target end")
    if not dates["forecast_available_at"].eq(origin+pd.Timedelta(days=1)).all(): errors.append("Wrong forecast timestamp")
    if origin.isna().any(): errors.append("Missing origin")
    else:
        expected=origin.map(lambda t:refit_origin(t,config))
        if not dates["refit_origin"].eq(expected).all(): errors.append("Wrong shared refit clock")
    if (ok & (dates["train_end"].isna() | dates["train_end"].gt(dates["refit_origin"]))).any(): errors.append("LEAKAGE: target/observation used after refit cutoff")
    if (ok & dates["train_feature_end"].gt(dates["refit_origin"])).any(): errors.append("LEAKAGE: future feature")
    supervised=fc["training_kind"].eq("supervised")
    if not fc["training_kind"].isin(["supervised","observations","combination"]).all(): errors.append("Unknown training kind")
    if (ok & (fc["n_train"]<config["backend1"]["evaluation"]["min_train_rows"])).any(): errors.append("Insufficient train rows for successful forecast")
    if (ok & supervised & dates["train_feature_end"].gt(dates["refit_origin"]-pd.to_timedelta(fc["horizon_days"],unit="D"))).any():
        errors.append("LEAKAGE: supervised feature origin has an unfinished target")
    if (ok & dates["train_end"].lt(dates["train_start"])).any(): errors.append("Training labels outside calendar window")
    lower=dates["refit_origin"]-pd.Timedelta(days=config["study"]["window_days"]-1)
    lower=lower.clip(lower=pd.Timestamp(config["data"]["research_start"],tz="UTC"))
    expanding=pd.Timestamp(config["data"]["research_start"],tz="UTC")
    expected_start=lower.where(fc["window"].eq("rolling"),expanding)
    if not dates["train_start"].eq(expected_start).all(): errors.append("Wrong calendar training window")
    p=pd.to_numeric(fc["rv_forecast_pct2"],errors="coerce")
    if (ok & (~np.isfinite(p) | p.le(0))).any(): errors.append("Successful forecast must be positive and finite")
    if (~ok & p.notna()).any(): errors.append("Failed forecast must not carry a prediction")
    if not np.allclose(fc.loc[ok,"volatility_forecast_pct"]**2,p.loc[ok],rtol=1e-10): errors.append("Wrong forecast units")
    if not fc["protocol_sha256"].eq(protocol_hash(config)).all(): errors.append("Protocol hash mismatch")
    if dataset_hash and not fc["dataset_sha256"].eq(dataset_hash).all(): errors.append("Dataset hash mismatch")
    keys=dataset[["symbol","origin_date"]].drop_duplicates().assign(found=True)
    if not fc.merge(keys,on=["symbol","origin_date"],how="left")["found"].fillna(False).all(): errors.append("Unknown origin/symbol")
    return errors
