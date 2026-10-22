"""Run Backend 2 on real data: shared HAR/GARCH/GJR evaluation and risk-volatility handoff."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.data.download import sha256,save_json
from src.models.har import HARRV
from src.models.garch import StudentTGARCH,StudentTGJR
from src.models.combine import combine_forecasts
from src.models.config import load_model_config,model_config_hash,validate_model_config
from src.evaluation.walkforward import Task,walk_forward
from src.evaluation.validate import validate_forecasts
from src.utils.config import ROOT,load_config,protocol_hash
from src.utils.io import write_table

MODELS={"har_rv":HARRV,"garch":StudentTGARCH,"gjr_garch":StudentTGJR}

def export_volatility(forecasts,folder):
    columns=["symbol","model","window","horizon_days","origin_date","target_start","target_date",
        "forecast_available_at","refit_origin","status","protocol_sha256","dataset_sha256"]
    out=forecasts[columns].copy()
    out["variance_pct2"]=forecasts["rv_forecast_pct2"];out["sigma_pct"]=forecasts["volatility_forecast_pct"]
    for col in ["mean_forecast_pct","nu","innovation_distribution","student_t_scale_pct","fit_signature"]:
        out[col]=forecasts[col] if col in forecasts else np.nan
    return write_table(out,folder/f"{forecasts['symbol'].iloc[0]}_{forecasts['model'].iloc[0]}.parquet")

def export_residuals(forecasts,dataset):
    valid=forecasts.loc[forecasts["horizon_days"].eq(1)&forecasts["status"].eq("ok")].copy()
    truth=dataset[["symbol","origin_date","ret_d"]].rename(columns={"origin_date":"target_date","ret_d":"realized_return_pct"})
    out=valid.merge(truth,on=["symbol","target_date"],how="left",validate="many_to_one")
    out["standardized_residual"]=(out["realized_return_pct"]-out["mean_forecast_pct"])/out["volatility_forecast_pct"]
    out["observable_at"]=out["target_date"]+pd.Timedelta(days=1)
    columns=["symbol","model","window","origin_date","target_date","observable_at","realized_return_pct",
        "mean_forecast_pct","volatility_forecast_pct","standardized_residual","nu","refit_origin"]
    return out[columns]

def run(config=None,model_config=None,segment="evaluation"):
    config=config or load_config();options=model_config or load_model_config()
    validate_model_config(options)
    path=ROOT/"data/processed/dataset.parquet";dataset=pd.read_parquet(path)
    meta=json.loads((ROOT/"data/processed/dataset_meta.json").read_text())
    if meta["dataset_sha256"]!=sha256(path) or meta["protocol_sha256"]!=protocol_hash(config):raise ValueError("Stale shared dataset; rebuild first")
    for name,expected in meta["inputs_sha256"].items():
        if sha256(ROOT/name)!=expected:raise ValueError("Changed source input: "+name)
    if segment not in ["evaluation","holdout"]:raise ValueError("Unknown segment")
    folder=ROOT/("outputs/forecasts" if segment=="evaluation" else "outputs/forecasts_holdout")
    volatility=ROOT/("outputs/volatility" if segment=="evaluation" else "outputs/volatility_holdout")
    diagnostics_dir=ROOT/("outputs/diagnostics" if segment=="evaluation" else "outputs/diagnostics_holdout")
    folder.mkdir(parents=True,exist_ok=True);volatility.mkdir(parents=True,exist_ok=True);diagnostics_dir.mkdir(parents=True,exist_ok=True)
    chosen=list(MODELS);diagnostics=[];parameters=[];har_diagnostics=[];outputs=[];fit_counts=[]
    for symbol,data in dataset.groupby("symbol"):
        forecasts={}
        for name in chosen:
            chunks=[]
            for scheme in ["rolling","expanding"]:
                cache={}
                if name=="har_rv":factory=lambda:HARRV(diagnostics=har_diagnostics,floor=options["garch"]["variance_floor"])
                else:
                    cls=MODELS[name]
                    factory=lambda cls=cls,cache=cache:cls(cache=cache,diagnostics=diagnostics,parameters=parameters,options=options["garch"])
                for h in [1,7]:
                    frame=walk_forward(data,factory,Task(h),config,scheme,segment)
                    chunks.append(frame)
                    print(f"{symbol}/{name}/{scheme}/h{h}: {int(frame['status'].eq('ok').sum())}/{len(frame)} valid forecasts",flush=True)
                if cache:fit_counts.append({"symbol":symbol,"model":name,"window":scheme,"unique_fits":len(cache)})
            fc=pd.concat(chunks,ignore_index=True)
            fc["protocol_sha256"]=protocol_hash(config);fc["dataset_sha256"]=meta["dataset_sha256"]
            fc["model_config_sha256"]=model_config_hash()
            errors=validate_forecasts(fc,dataset,config,meta["dataset_sha256"],name)
            if errors:raise ValueError(errors)
            write_table(fc,folder/f"{symbol}_{name}.parquet");export_volatility(fc,volatility)
            forecasts[name]=fc;outputs.append(fc)
        components=options["combination"]["components"]
        missing=[name for name in components if name not in forecasts and not (folder/f"{symbol}_{name}.parquet").exists()]
        if missing:raise ValueError(f"Missing required combination inputs for {symbol}: {missing}")
        if all(name in forecasts or (folder/f"{symbol}_{name}.parquet").exists() for name in components):
            pieces={name:forecasts[name] if name in forecasts else pd.read_parquet(folder/f"{symbol}_{name}.parquet") for name in components}
            for name,piece in pieces.items():
                errors=validate_forecasts(piece,dataset,config,meta["dataset_sha256"],name)
                if errors:raise ValueError(errors)
            combined=combine_forecasts(pieces,components,options["combination"]["model_name"])
            combined["model_config_sha256"]=model_config_hash()
            errors=validate_forecasts(combined,dataset,config,meta["dataset_sha256"],"combination")
            if errors:raise ValueError(errors)
            write_table(combined,folder/f"{symbol}_{options['combination']['model_name']}.parquet")
            export_volatility(combined,volatility);outputs.append(combined)
    pd.DataFrame(diagnostics).to_csv(diagnostics_dir/"garch_fit_diagnostics.csv",index=False)
    pd.DataFrame(parameters).to_csv(diagnostics_dir/"garch_parameters.csv",index=False)
    pd.DataFrame(har_diagnostics).to_csv(diagnostics_dir/"har_fit_diagnostics.csv",index=False)
    all_forecasts=pd.concat(outputs,ignore_index=True)
    write_table(export_residuals(all_forecasts,dataset),diagnostics_dir/"oos_standardized_residuals.parquet")
    save_json(diagnostics_dir/"run_summary.json",{"segment":segment,"models":chosen,"forecast_rows":len(all_forecasts),
        "status_counts":all_forecasts["status"].value_counts().to_dict(),"fit_cache_counts":fit_counts,
        "protocol_sha256":protocol_hash(config),"dataset_sha256":meta["dataset_sha256"],
        "model_config_sha256":model_config_hash(),"holdout_evaluated":segment=="holdout",
        "risk_note":"h=7 sigma is sqrt(sum variance); aggregate return is not exactly Student-t"})
    return all_forecasts

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-holdout",action="store_true")
    args=parser.parse_args();lock=ROOT/"outputs/final_holdout_backend2.json"
    if args.final_holdout:
        if lock.exists():raise ValueError("Final Backend 2 holdout run already recorded")
        save_json(lock,{"state":"started","model_config_sha256":model_config_hash()})
    run(segment="holdout" if args.final_holdout else "evaluation")
    if args.final_holdout:save_json(lock,{"state":"completed","model_config_sha256":model_config_hash()})

if __name__=="__main__":main()
