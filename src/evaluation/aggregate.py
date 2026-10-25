"""Validate real forecasts, compare on common dates, export numerical tables and figures."""
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.data.download import sha256,save_json
from src.evaluation.dm import dm_test
from src.evaluation.metrics import add_losses,summarize
from src.evaluation.validate import truth_table,validate_forecasts
from src.utils.config import ROOT,load_config,protocol_hash

GROUP=["symbol","horizon_days","window"]

def load_all_forecasts(folder,dataset,config,dataset_hash):
    parts=[]
    for path in sorted(folder.glob("*.parquet")):
        if path.stem.endswith("_risk"): continue
        fc=pd.read_parquet(path)
        errors=validate_forecasts(fc,dataset,config,dataset_hash,path.name)
        if errors: raise ValueError(f"{path.name}: {errors}")
        parts.append(fc)
    if not parts: raise ValueError("No forecast files found")
    result=pd.concat(parts,ignore_index=True)
    errors=validate_forecasts(result,dataset,config,dataset_hash,"all forecast files")
    if errors: raise ValueError(errors)
    return result

def build_eval_frame(fc,dataset,segment="evaluation"):
    truth=truth_table(dataset,sorted(fc["horizon_days"].unique()))
    merged=fc.merge(truth,on=["symbol","origin_date","horizon_days"],how="left",validate="many_to_one")
    merged=merged.loc[merged["target_segment"].eq(segment)].copy()
    evaluations=[];coverage=[]
    for keys,group in merged.groupby(GROUP):
        required=group["model"].nunique()
        eligible=group.loc[group["status"].eq("ok") & group["y_true"].gt(0) & np.isfinite(group["y_true"])].copy()
        counts=eligible.groupby("origin_date")["model"].nunique()
        common=counts.index[counts.eq(required)]
        common_rows=eligible.loc[eligible["origin_date"].isin(common)].copy()
        evaluations.append(common_rows)
        model_set=",".join(sorted(group["model"].unique()))
        for model,part in group.groupby("model"):
            coverage.append(dict(zip(GROUP,keys),model=model,n_requested=len(part),
                n_success=int(part["status"].eq("ok").sum()),n_valid_target=int(part["y_true"].gt(0).sum()),
                n_common=len(common),models_compared=model_set,
                core_models_complete=set(["har_rv","garch","gjr_garch","xgboost"]).issubset(group["model"].unique())))
    result=pd.concat(evaluations,ignore_index=True)
    if result.empty: raise ValueError("No common valid out-of-sample forecast dates")
    return add_losses(result),pd.DataFrame(coverage)

def comparison_table(ev,benchmark):
    records=[]
    for keys,group in ev.groupby(GROUP+["model"]):
        records.append(dict(zip(GROUP+["model"],keys),**summarize(group).to_dict()))
    result=pd.DataFrame(records)
    for _,indices in result.groupby(GROUP).groups.items():
        base=result.loc[indices].loc[result.loc[indices,"model"].eq(benchmark)]
        for metric in ["RMSE","MAE","QLIKE"]:
            value=base[metric].iloc[0] if len(base) else np.nan
            result.loc[indices,metric+"_relative_to_har"]=result.loc[indices,metric]/value if value>0 else np.nan
    return result

def dm_table(ev,benchmark,config,by_regime=False):
    rows=[];group_cols=GROUP+(["regime"] if by_regime else [])
    for keys,group in ev.groupby(group_cols):
        for metric in ["qlike","se","ae"]:
            pair=group.pivot(index="origin_date",columns="model",values=metric).sort_index()
            if benchmark not in pair: continue
            for model in pair.columns:
                if model==benchmark: continue
                result=dm_test(pair[model],pair[benchmark],h=int(keys[1]),dates=pair.index,
                    min_n=config["backend1"]["evaluation"]["dm_min_observations"])
                rows.append(dict(zip(group_cols,keys),model=model,benchmark=benchmark,loss=metric,**result))
    columns=group_cols+["model","benchmark","loss","n","mean_diff","stat","p_value","status"]
    return pd.DataFrame(rows,columns=columns)

def make_figures(ev,config,directory):
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9})
    for (symbol,h,scheme),group in ev.groupby(GROUP):
        prefix=f"backend1_{symbol}_{scheme}_h{h}"
        actual=group.drop_duplicates("target_date").set_index("target_date")["y_true"].sort_index()
        grid=pd.date_range(actual.index.min(),actual.index.max(),tz="UTC",freq="D")
        fig,axes=plt.subplots(2,1,figsize=(11,6),sharex=True,layout="constrained")
        for ax,sqrt in zip(axes,[False,True]):
            values=actual.reindex(grid);ax.plot(grid,np.sqrt(values) if sqrt else values,color="black",lw=1,label="Actual")
            for model,part in group.groupby("model"):
                values=part.set_index("target_date")["rv_forecast_pct2"].reindex(grid)
                ax.plot(grid,np.sqrt(values) if sqrt else values,lw=.7,alpha=.8,label=model)
            ax.set_ylabel("Volatility (%)" if sqrt else "Variance (%²)");ax.legend(ncol=4,fontsize=8)
        axes[0].set_title(f"{symbol} | {scheme} | {h}-day variance | {actual.index.min():%Y-%m-%d} to {actual.index.max():%Y-%m-%d}")
        axes[-1].set_xlabel("Target end (UTC)");fig.savefig(directory/f"{prefix}_forecast_vs_actual.png",dpi=130);plt.close(fig)
        losses=group.pivot(index="origin_date",columns="model",values="qlike").sort_index()
        losses=losses.reindex(pd.date_range(losses.index.min(),losses.index.max(),tz="UTC",freq="D"))
        days=config["backend1"]["evaluation"]["rolling_loss_days"]
        ax=losses.rolling(f"{days}D",min_periods=30).mean().plot(figsize=(11,3.5),lw=.8)
        ax.set_title(f"{symbol} | {scheme} | h={h} | {days}-calendar-day rolling QLIKE")
        ax.figure.tight_layout();ax.figure.savefig(directory/f"{prefix}_rolling_qlike.png",dpi=130);plt.close(ax.figure)
        by=group.groupby(["regime","model"])["qlike"].mean().unstack("model")
        ax=by.plot.bar(figsize=(9,3.5),rot=0)
        ax.set_title(f"{symbol} | {scheme} | h={h} | QLIKE by origin regime")
        ax.figure.tight_layout();ax.figure.savefig(directory/f"{prefix}_regimes.png",dpi=130);plt.close(ax.figure)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--final-holdout",action="store_true")
    args=parser.parse_args(argv);cfg=load_config();segment="holdout" if args.final_holdout else "evaluation"
    path=ROOT/"data/processed/dataset.parquet";ds=pd.read_parquet(path)
    meta=json.loads((ROOT/"data/processed/dataset_meta.json").read_text())
    if meta["dataset_sha256"]!=sha256(path) or meta["protocol_sha256"]!=protocol_hash(cfg): raise ValueError("Stale dataset")
    if args.final_holdout:
        lock=ROOT/"outputs/final_holdout_scoring.json"
        if lock.exists(): raise ValueError("Holdout was already scored; inspect stored results")
        save_json(lock,{"state":"started","protocol_sha256":protocol_hash(cfg)})
    folder=ROOT/("outputs/forecasts_holdout" if args.final_holdout else "outputs/forecasts")
    fc=load_all_forecasts(folder,ds,cfg,meta["dataset_sha256"])
    ev,coverage=build_eval_frame(fc,ds,segment)
    out=ROOT/("outputs/holdout_tables" if args.final_holdout else "outputs/tables")
    figs=ROOT/("outputs/holdout_figures" if args.final_holdout else "outputs/figures")
    out.mkdir(parents=True,exist_ok=True);figs.mkdir(parents=True,exist_ok=True)
    benchmark=cfg["backend1"]["evaluation"]["benchmark"]
    comparison=comparison_table(ev,benchmark)
    regime_rows=[dict(zip(GROUP+["regime","model"],keys),**summarize(group).to_dict())
        for keys,group in ev.groupby(GROUP+["regime","model"])]
    tables={"model_comparison":comparison,"dm_vs_benchmark":dm_table(ev,benchmark,cfg),
        "regime_performance":pd.DataFrame(regime_rows),"dm_by_regime":dm_table(ev,benchmark,cfg,True),
        "forecast_coverage":coverage}
    available=fc.merge(truth_table(ds,sorted(fc["horizon_days"].unique())),
        on=["symbol","origin_date","horizon_days"],how="left",validate="many_to_one")
    available=available.loc[available.target_segment.eq(segment)&available.status.eq("ok")&
        available.y_true.gt(0)&np.isfinite(available.y_true)].copy()
    available=add_losses(available)
    tables["model_comparison_available_sample"]=pd.DataFrame([
        dict(zip(GROUP+["model"],keys),**summarize(group).to_dict(),sample="model_specific_not_common")
        for keys,group in available.groupby(GROUP+["model"])])
    for name,table in tables.items(): table.to_csv(out/f"{name}.csv",index=False)
    availability=[]
    for model in ["har_rv","garch","gjr_garch","xgboost"]:
        availability.append({"model":model,"status":"available" if model in set(fc["model"]) else "awaiting_team_forecast",
            "note":"Backend 2 OLS" if model=="har_rv" else
                "Backend 2 arch Student-t" if model in ["garch","gjr_garch"] else "Backend 3 seeded CPU XGBoost"})
    pd.DataFrame(availability).to_csv(out/"model_availability.csv",index=False)
    counts=ev.drop_duplicates(GROUP+["origin_date"]).groupby(GROUP+["regime"]).size().rename("n_common_dates").reset_index()
    counts.to_csv(out/"regime_counts.csv",index=False)
    make_figures(ev,cfg,figs)
    save_json(out/"backend1_validation.json",{"status":"passed","data_source":meta["data_source"],
        "protocol_sha256":protocol_hash(cfg),"dataset_sha256":meta["dataset_sha256"],"segment":segment,
        "forecast_rows":len(fc),"common_scored_rows":len(ev),"models":sorted(fc["model"].unique()),
        "full_core_comparison_ready":all(x["status"]=="available" for x in availability) and bool(coverage["core_models_complete"].all()),
        "macro_predictive_use":False,"turnover_is_proxy":True,"holdout_scored":args.final_holdout})
    if args.final_holdout: save_json(lock,{"state":"completed","protocol_sha256":protocol_hash(cfg)})
    print(comparison.round(4).to_string(index=False),flush=True)

if __name__=="__main__": main()
