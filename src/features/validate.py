"""Validate real feature targets against independent intraday return sums."""
import json
import numpy as np
import pandas as pd
from src.data.download import save_json,sha256
from src.features.schema import FEATURE_COLS,y_col
from src.utils.config import ROOT,load_config,protocol_hash

def validate():
    config=load_config();path=ROOT/"data/processed/dataset.parquet"
    data=pd.read_parquet(path);meta=json.loads((ROOT/"data/processed/dataset_meta.json").read_text())
    assert sha256(path)==meta["dataset_sha256"] and protocol_hash(config)==meta["protocol_sha256"]
    for name,expected in meta["inputs_sha256"].items(): assert sha256(ROOT/name)==expected,name
    assert not data.duplicated(["symbol","origin_date"]).any()
    checks=[]
    for symbol,d in data.groupby("symbol",sort=False):
        d=d.reset_index(drop=True)
        expected=pd.date_range(config["data"]["start"],config["data"]["end"],tz="UTC",freq="D")
        pd.testing.assert_index_equal(pd.DatetimeIndex(d["origin_date"]),expected,check_names=False)
        assert d["feature_available_at"].eq(d["origin_date"]+pd.Timedelta(days=1)).all()
        bars=pd.read_parquet(ROOT/f"data/interim/{symbol}_5m_clean.parquet",columns=["open_time","close"])
        adjacent=bars["open_time"].diff().eq(pd.Timedelta(minutes=5))
        returns=(100*np.log(bars["close"]/bars["close"].shift(1))).where(adjacent)
        rv=returns.pow(2).groupby(bars["open_time"].dt.floor("D")).sum(min_count=288).reindex(expected)
        rv=rv.where(d["eligible_rv"].to_numpy())
        np.testing.assert_allclose(rv,d["rv_d"],rtol=1e-12,atol=1e-12,equal_nan=True)
        for h in [1,7]:
            target=rv.rolling(h,min_periods=h).sum().shift(-h)
            np.testing.assert_allclose(target,d[y_col(h)],rtol=1e-12,atol=1e-12,equal_nan=True)
        assert np.isfinite(d[FEATURE_COLS].dropna().to_numpy()).all()
        checks.append({"symbol":symbol,"calendar_days":len(d),"main_feature_complete":int(d[FEATURE_COLS].notna().all(axis=1).sum()),
            "valid_h1_targets":int(d[y_col(1)].notna().sum()),"valid_h7_targets":int(d[y_col(7)].notna().sum())})
    schedule=pd.read_parquet(ROOT/"data/processed/forecast_schedule.parquet")
    assert schedule["refit_origin"].le(schedule["origin_date"]).all()
    anchor=pd.Timestamp(config["study"]["refit_anchor_origin_date"],tz="UTC")
    assert (schedule["refit_origin"]-anchor).dt.days.mod(5).eq(0).all()
    assert schedule["is_refit"].eq(schedule["origin_date"].eq(schedule["refit_origin"])).all()
    result={"status":"passed","independent_intraday_rv_check":True,"protocol_sha256":protocol_hash(config),
        "dataset_sha256":meta["dataset_sha256"],"checks":checks,"schedule_rows":len(schedule),"holdout_scored":False}
    save_json(ROOT/"outputs/tables/feature_validation.json",result)
    print(json.dumps(result,indent=2),flush=True)
    return result

if __name__=="__main__": validate()
