"""Calendar-anchored walk-forward; generic adapters receive no future target in predict/history."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from src.features.schema import FEATURE_COLS,y_col,ylog_col

FORECAST_COLS=["symbol","model","horizon_days","window","origin_date","target_start","target_date",
    "forecast_available_at","rv_forecast_pct2","volatility_forecast_pct","refit_origin","train_start",
    "train_end","train_feature_end","n_train","training_kind","status"]

@dataclass(frozen=True)
class Task:
    horizon:int
    @property
    def y_col(self): return y_col(self.horizon)
    @property
    def ylog_col(self): return ylog_col(self.horizon)

class BaseModel:
    name="base"
    features=[]
    requires_target=True
    def fit(self,train,task): raise NotImplementedError
    def predict(self,test,task,history=None): raise NotImplementedError

def refit_origin(origin,config):
    anchor=pd.Timestamp(config["study"]["refit_anchor_origin_date"],tz="UTC")
    if origin<anchor: raise ValueError("Evaluation origin precedes the shared refit anchor")
    step=config["study"]["refit_every_days"]
    return anchor+pd.Timedelta(days=((origin-anchor).days//step)*step)

def select_training(data,task,features,fit_origin,config,scheme="rolling",requires_target=True):
    if scheme not in ("rolling","expanding"): raise ValueError("Unknown window")
    if not set(features).issubset(FEATURE_COLS): raise ValueError("Only declared causal main features are allowed")
    lower=pd.Timestamp(config["data"]["research_start"],tz="UTC")
    if scheme=="rolling": lower=max(lower,fit_origin-pd.Timedelta(days=config["study"]["window_days"]-1))
    if requires_target:
        end=data[f"target_end_h{task.horizon}"]
        mask=end.between(lower,fit_origin) & data[f"target_start_h{task.horizon}"].ge(lower)
        mask &= data[task.y_col].gt(0) & np.isfinite(data[task.y_col])
        # A multi-day label must stay inside one agreed study segment.
        mask &= ~data[f"target_segment_h{task.horizon}"].isin(["pre_sample","cross_segment","out_of_scope"])
    else:
        end=data["origin_date"]
        mask=end.between(lower,fit_origin)
    if features: mask &= np.isfinite(data[features]).all(axis=1)
    train=data.loc[mask].copy()
    label_end=end.loc[mask].max() if len(train) else pd.NaT
    if not requires_target:
        train=train[[c for c in train.columns if not c.startswith(("y_","target_"))]]
    return train,lower,label_end

def iter_splits(data,task,features,config,scheme="rolling",segment="evaluation",requires_target=True):
    if segment not in ("evaluation","holdout"): raise ValueError("Choose evaluation or explicit final holdout")
    d=data.sort_values("origin_date").reset_index(drop=True)
    if d["origin_date"].duplicated().any(): raise ValueError("One symbol per split, unique UTC origins required")
    selected=d[f"target_segment_h{task.horizon}"].eq(segment)
    selected &= d[f"target_end_h{task.horizon}"].le(pd.Timestamp(config["data"]["end"],tz="UTC"))
    cache=None;last=None
    for _,row in d.loc[selected].iterrows():
        fit=refit_origin(row["origin_date"],config)
        changed=fit!=last
        if changed:
            cache=select_training(d,task,features,fit,config,scheme,requires_target)
            last=fit
        train,lower,label_end=cache
        yield train,row,{"refit_origin":fit,"train_start":lower,"train_end":label_end,"is_refit":row["origin_date"]==fit,"needs_fit":changed}

def walk_forward(data,model_factory,task,config,scheme="rolling",segment="evaluation"):
    template=model_factory();features=list(template.features);requires_target=template.requires_target
    d=data.sort_values("origin_date").reset_index(drop=True)
    model=None;rows=[];n_train=0;feature_end=pd.NaT
    for train,row,meta in iter_splits(d,task,features,config,scheme,segment,requires_target):
        if meta["needs_fit"]:
            n_train=len(train);feature_end=train["origin_date"].max() if n_train else pd.NaT
            model=None
            if n_train>=config["backend1"]["evaluation"]["min_train_rows"]:
                model=model_factory();model.fit(train,task)
        status="ok";prediction=np.nan
        if model is None: status="insufficient_train"
        elif features and not np.isfinite(row[features].astype(float)).all(): status="missing_features"
        else:
            columns=["symbol","origin_date",*features]
            test=pd.DataFrame([row[columns]])
            history=d.loc[d["origin_date"].le(row["origin_date"]),
                [c for c in d.columns if not c.startswith(("y_","target_"))]].copy()
            values=np.asarray(model.predict(test,task,history=history),dtype=float)
            if values.shape!=(1,): raise ValueError("predict must return exactly one variance for each input row")
            prediction=float(values[0])
            if not np.isfinite(prediction) or prediction<=0: raise ValueError(f"{template.name}: invalid variance forecast")
        rows.append({"symbol":row["symbol"],"model":template.name,"horizon_days":task.horizon,
            "window":scheme,"origin_date":row["origin_date"],"target_start":row[f"target_start_h{task.horizon}"],
            "target_date":row[f"target_end_h{task.horizon}"],"forecast_available_at":row["origin_date"]+pd.Timedelta(days=1),
            "rv_forecast_pct2":prediction,"volatility_forecast_pct":np.sqrt(prediction),
            "refit_origin":meta["refit_origin"],"train_start":meta["train_start"],"train_end":meta["train_end"],
            "train_feature_end":feature_end,"n_train":n_train,"training_kind":"supervised" if requires_target else "observations",
            "status":status})
    return pd.DataFrame(rows,columns=FORECAST_COLS)

def make_schedule(dataset,config):
    parts=[]
    for symbol,d in dataset.groupby("symbol"):
        for h in [config["study"]["main_horizon_days"],*config["study"]["sensitivity_horizon_days"]]:
            mask=d[f"target_segment_h{h}"].isin(["evaluation","holdout"])
            mask &= d[f"target_end_h{h}"].le(pd.Timestamp(config["data"]["end"],tz="UTC"))
            chosen=d.loc[mask]
            for scheme in ["rolling","expanding"]:
                frame=chosen[["symbol","origin_date",f"target_start_h{h}",f"target_end_h{h}",f"target_segment_h{h}",f"target_valid_h{h}"]].rename(
                    columns={f"target_start_h{h}":"target_start",f"target_end_h{h}":"target_date",f"target_segment_h{h}":"target_segment",f"target_valid_h{h}":"target_valid"}).copy()
                frame["horizon_days"]=h;frame["window"]=scheme
                frame["refit_origin"]=frame["origin_date"].map(lambda t:refit_origin(t,config))
                lower=pd.Timestamp(config["data"]["research_start"],tz="UTC")
                frame["train_start"]=(frame["refit_origin"]-pd.Timedelta(days=config["study"]["window_days"]-1)).clip(lower=lower) if scheme=="rolling" else lower
                frame["label_cutoff"]=frame["refit_origin"]
                frame["is_refit"]=frame["origin_date"].eq(frame["refit_origin"])
                parts.append(frame)
    return pd.concat(parts,ignore_index=True)
