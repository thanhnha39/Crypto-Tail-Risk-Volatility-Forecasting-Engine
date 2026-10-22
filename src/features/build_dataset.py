"""Build the real-data feature handoff: python -m src.features.build_dataset."""
import json
from datetime import datetime,timezone
import pandas as pd
from src.data.download import sha256,save_json
from src.features.build_features import build_features
from src.features.schema import FEATURE_COLS,MACRO_COLS
from src.utils.config import ROOT,load_config,protocol_hash
from src.utils.io import write_table

def main():
    cfg=load_config();parts=[];thresholds=[];inputs={}
    if cfg["backend1"]["features"]["macro_in_main"] or cfg["study"]["macro_in_main_model"]:
        raise ValueError("Main model macro features are prohibited by the agreed protocol")
    for symbol in cfg["data"]["symbols"]:
        path=ROOT/f"data/interim/{symbol}_daily_reference_qa.parquet"
        inputs[str(path.relative_to(ROOT))]=sha256(path)
        frame,threshold=build_features(pd.read_parquet(path),cfg)
        parts.append(frame);thresholds.append(threshold)
    ds=pd.concat(parts,ignore_index=True)
    path=write_table(ds,ROOT/"data/processed/dataset.parquet")
    save_json(ROOT/"data/processed/dataset_meta.json",{
        "created_at_utc":datetime.now(timezone.utc).isoformat(),"data_source":"binance_spot_real_snapshot",
        "snapshot_id":cfg["snapshot"]["id"],"protocol_sha256":protocol_hash(cfg),"dataset_sha256":sha256(path),
        "inputs_sha256":inputs,"rows":len(ds),"column_dtypes":{col:str(dtype) for col,dtype in ds.dtypes.items()},"feature_columns":FEATURE_COLS,"macro_excluded_columns":MACRO_COLS,
        "turnover_is_proxy":True,"target_7d_aggregation":"sum","target_unit":"percent_squared",
        "missing_data":"calendar retained; no RV filling/scaling; no winsorization", "holdout_evaluated":False})
    save_json(ROOT/"data/processed/regime_thresholds.json",thresholds)
    ds[["symbol","origin_date","origin_segment","regime","regime_rv22_pct2","ret_90d_pct"]].to_csv(ROOT/"data/processed/regime_labels.csv",index=False)
    # Convenient root-level deliverable, sourced from exactly the same frame.
    ds[["symbol","origin_date","origin_segment","regime"]].to_csv(ROOT/"outputs/tables/regime_labels.csv",index=False)
    print(f"Real-data dataset written: {len(ds)} rows, {len(ds.columns)} columns; no holdout evaluation.")
    return ds

if __name__=="__main__": main()
