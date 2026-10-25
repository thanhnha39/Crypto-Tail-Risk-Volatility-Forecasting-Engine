"""Run verified baseline forecasts on evaluation only by default; never silently score holdout."""
import argparse
import json
import pandas as pd
from src.data.download import sha256,save_json
from src.evaluation.baselines import BASELINES
from src.evaluation.walkforward import Task,walk_forward,make_schedule
from src.evaluation.validate import validate_forecasts
from src.utils.config import ROOT,load_config,protocol_hash
from src.utils.io import write_table

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-holdout",action="store_true",help="Explicit final run only; do not use to tune models")
    args=parser.parse_args()
    config=load_config();path=ROOT/"data/processed/dataset.parquet"
    ds=pd.read_parquet(path);meta=json.loads((ROOT/"data/processed/dataset_meta.json").read_text())
    if meta["protocol_sha256"]!=protocol_hash(config) or meta["dataset_sha256"]!=sha256(path): raise ValueError("Rebuild stale dataset")
    segment="holdout" if args.final_holdout else "evaluation"
    lock=ROOT/"outputs/final_holdout_run.json"
    if args.final_holdout:
        if lock.exists(): raise ValueError("Final holdout run already recorded; inspect it rather than rerun")
        save_json(lock,{"state":"started","protocol_sha256":protocol_hash(config),"dataset_sha256":meta["dataset_sha256"]})
    schedule=make_schedule(ds,config)
    if args.final_holdout:
        pd.testing.assert_frame_equal(schedule,pd.read_parquet(ROOT/"data/processed/forecast_schedule.parquet"))
    else:write_table(schedule,ROOT/"data/processed/forecast_schedule.parquet")
    folder=ROOT/("outputs/forecasts_holdout" if args.final_holdout else "outputs/forecasts")
    folder.mkdir(parents=True,exist_ok=True)
    for symbol,d in ds.groupby("symbol"):
        for name in config["backend1"]["evaluation"]["baseline_models"]:
            chunks=[]
            for scheme in ["rolling","expanding"]:
                for h in [1,7]:
                    chunks.append(walk_forward(d,BASELINES[name],Task(h),config,scheme,segment))
            fc=pd.concat(chunks,ignore_index=True)
            fc["protocol_sha256"]=protocol_hash(config);fc["dataset_sha256"]=meta["dataset_sha256"]
            errors=validate_forecasts(fc,ds,config,meta["dataset_sha256"],name)
            if errors: raise ValueError(errors)
            write_table(fc,folder/f"{symbol}_{name}.parquet")
            print(f"{symbol}/{name}: {len(fc)} rows, {int(fc['status'].eq('ok').sum())} successful",flush=True)
    if args.final_holdout: save_json(lock,{"state":"completed","protocol_sha256":protocol_hash(config),"dataset_sha256":meta["dataset_sha256"]})

if __name__=="__main__": main()
