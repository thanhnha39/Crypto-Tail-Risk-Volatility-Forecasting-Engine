"""Behavioral leakage tests; artificial daily fixtures are never used as research results."""
import copy
from functools import lru_cache
import unittest
import numpy as np
import pandas as pd
from scipy import stats
from src.utils.config import load_config,protocol_hash
from src.features.build_features import build_features
from src.features.schema import FEATURE_COLS,y_col
from src.evaluation.walkforward import Task,walk_forward,select_training,refit_origin,BaseModel
from src.evaluation.baselines import HARRV,NaiveRW
from src.evaluation.validate import validate_forecasts
from src.evaluation.aggregate import build_eval_frame
from src.evaluation.dm import dm_test
from src.evaluation.metrics import qlike_loss

CFG=load_config()

def fixture():
    dates=pd.date_range("2018-12-01","2022-06-30",tz="UTC",freq="D")
    rng=np.random.default_rng(19);i=np.arange(len(dates));close=100*np.exp(.0002*i+.02*np.sin(i/30))
    rv=4+.8*np.sin(i/7)+rng.uniform(0,.3,len(i))
    return pd.DataFrame({"symbol":"BTCUSDT","date":dates,"close":close,"high":close*1.02,"low":close*.98,
        "rv_reference_pct2":rv,"eligible_rv":True,"valid_bars":288,"valid_adjacent_returns":288,
        "return_daily_pct_qa":pd.Series(100*np.log(close)).diff(),"quote_volume":1e6+1000*i})

@lru_cache(maxsize=1)
def dataset(): return build_features(fixture(),CFG)[0]

class LeakageTests(unittest.TestCase):
    def test_future_removal_and_corruption_leave_past_features_unchanged(self):
        raw=fixture();cut=pd.Timestamp("2021-05-12",tz="UTC")
        full,threshold=build_features(raw,CFG)
        truncated,_=build_features(raw.loc[raw.date.le(cut)],CFG)
        damaged=raw.copy();damaged.loc[damaged.date.gt(cut),["close","high","low","rv_reference_pct2","quote_volume"]]=1e8
        changed,new_threshold=build_features(damaged,CFG)
        columns=FEATURE_COLS+["regime","regime_rv22_pct2"]
        pd.testing.assert_frame_equal(full.loc[full.origin_date.le(cut),columns].reset_index(drop=True),truncated[columns].reset_index(drop=True))
        pd.testing.assert_frame_equal(full.loc[full.origin_date.le(cut),columns],changed.loc[changed.origin_date.le(cut),columns])
        self.assertEqual(threshold,new_threshold)

    def test_missing_calendar_day_is_not_skipped_or_scaled(self):
        raw=fixture();day=pd.Timestamp("2021-02-10",tz="UTC");bad=raw.date.eq(day)
        raw.loc[bad,"rv_reference_pct2"]=np.nan;raw.loc[bad,"eligible_rv"]=False;raw.loc[bad,"valid_bars"]=287
        frame,_=build_features(raw,CFG)
        self.assertEqual(len(frame),len(raw))
        self.assertTrue(frame.loc[frame.origin_date.between(day,day+pd.Timedelta(days=21)),"rv_m"].isna().all())
        self.assertTrue(frame.loc[frame.origin_date.eq(day-pd.Timedelta(days=1)),y_col(7)].isna().all())
        with self.assertRaises(ValueError): build_features(raw.loc[~bad],CFG)

    def test_targets_sum_and_cross_period_labels(self):
        frame=dataset();pos=frame.index[frame.origin_date.eq(pd.Timestamp("2021-03-01",tz="UTC"))][0]
        self.assertAlmostEqual(frame.loc[pos,y_col(7)],frame.loc[pos+1:pos+7,"rv_d"].sum())
        self.assertAlmostEqual(frame.loc[pos,y_col(1)],frame.loc[pos+1,"rv_d"])
        self.assertTrue(frame[y_col(7)].tail(7).isna().all())
        self.assertEqual(frame.loc[frame.origin_date.eq(pd.Timestamp("2020-12-30",tz="UTC")),"target_segment_h7"].iloc[0],"cross_segment")
        self.assertEqual(frame.loc[frame.origin_date.eq(pd.Timestamp("2020-12-31",tz="UTC")),"target_segment_h1"].iloc[0],"evaluation")
        self.assertFalse(set(FEATURE_COLS)&{col for col in frame if col.startswith("y_")})

    def test_macro_is_not_in_main_features(self):
        self.assertFalse(any("vix" in col or "usd" in col for col in FEATURE_COLS))

    def test_regime_threshold_is_frozen_and_unavailable_during_warmup(self):
        raw=fixture();frame,threshold=build_features(raw,CFG)
        self.assertTrue(frame.loc[frame.origin_date.lt(pd.Timestamp("2020-12-31",tz="UTC")),"regime"].eq("unclassified").all())
        warm=raw.date.between(pd.Timestamp("2019-01-01",tz="UTC"),pd.Timestamp("2020-12-31",tz="UTC"))
        expected=raw.rv_reference_pct2.rolling(22,min_periods=22).mean().loc[warm].quantile(.9)
        self.assertAlmostEqual(threshold["crisis_threshold_pct2"],expected)

    def test_calendar_window_and_label_availability(self):
        frame=dataset();fit=pd.Timestamp("2021-05-10",tz="UTC")
        for h in [1,7]:
            train,start,end=select_training(frame,Task(h),["rv_d"],fit,CFG,"rolling")
            self.assertEqual(start,fit-pd.Timedelta(days=729))
            self.assertLessEqual(end,fit)
            self.assertTrue(train[f"target_end_h{h}"].le(fit).all())
            damaged=frame.copy();damaged.loc[damaged[f"target_end_h{h}"].gt(fit),y_col(h)]=1e10
            other,_,_=select_training(damaged,Task(h),["rv_d"],fit,CFG,"rolling")
            pd.testing.assert_frame_equal(train,other)

    def test_refit_clock_does_not_depend_on_missing_features(self):
        c=copy.deepcopy(CFG);c["data"]["research_end"]="2021-01-15"
        # Limit evaluation selection by deterministic task label for a short fixture run.
        d=dataset().copy();d.loc[d.origin_date.gt(pd.Timestamp("2021-01-14",tz="UTC")),"target_segment_h1"]="holdout"
        one=walk_forward(d,NaiveRW,Task(1),c)
        d.loc[d.origin_date.eq(pd.Timestamp("2021-01-02",tz="UTC")),"rv_d"]=np.nan
        two=walk_forward(d,NaiveRW,Task(1),c)
        self.assertEqual(one.refit_origin.tolist(),two.refit_origin.tolist())
        for day in two.origin_date:
            self.assertEqual(refit_origin(day,c),pd.Timestamp("2020-12-31",tz="UTC")+pd.Timedelta(days=((day-pd.Timestamp("2020-12-31",tz="UTC")).days//5)*5))

    def test_forecasts_ignore_unobserved_targets_and_future_features(self):
        cut=pd.Timestamp("2021-03-14",tz="UTC")
        for h in [1,7]:
            data=dataset().copy();data.loc[data.origin_date.gt(cut),f"target_segment_h{h}"]="holdout"
            before=walk_forward(data,HARRV,Task(h),CFG)
            changed=data.copy();changed.loc[changed[f"target_end_h{h}"].gt(cut),y_col(h)]=1e9
            changed.loc[changed.origin_date.gt(cut),FEATURE_COLS]=1e7
            after=walk_forward(changed,HARRV,Task(h),CFG)
            pd.testing.assert_frame_equal(before,after)

    def test_adapter_predict_and_history_do_not_receive_future_labels(self):
        class Inspect(NaiveRW):
            def predict(self,test,task,history=None):
                assert not any(col.startswith(("y_","target_")) for col in test)
                assert not any(col.startswith(("y_","target_")) for col in history)
                assert history.origin_date.max()<=test.origin_date.iloc[0]
                return super().predict(test,task,history)
        d=dataset().copy();d.loc[d.origin_date.gt(pd.Timestamp("2021-01-10",tz="UTC")),"target_segment_h1"]="holdout"
        self.assertGreater(len(walk_forward(d,Inspect,Task(1),CFG)),0)

    def test_forecast_validator_and_naive_seven_day_units(self):
        d=dataset().copy();d.loc[d.origin_date.gt(pd.Timestamp("2021-01-15",tz="UTC")),"target_segment_h7"]="holdout"
        fc=walk_forward(d,NaiveRW,Task(7),CFG)
        fc["protocol_sha256"]=protocol_hash(CFG);fc["dataset_sha256"]="fixture"
        self.assertEqual(validate_forecasts(fc,d,CFG,"fixture"),[])
        expected=d.set_index("origin_date").loc[fc.origin_date,"rv_d"].to_numpy()*7
        np.testing.assert_allclose(fc.rv_forecast_pct2,expected)
        bad=fc.copy();bad["train_end"]=bad["refit_origin"]+pd.Timedelta(days=1)
        self.assertTrue(any("LEAKAGE" in error for error in validate_forecasts(bad,d,CFG,"fixture")))
        bad=fc.copy();bad["protocol_sha256"]="wrong"
        self.assertTrue(validate_forecasts(bad,d,CFG,"fixture"))

    def test_common_sample_excludes_failed_model_dates(self):
        d=dataset().copy();d.loc[d.origin_date.gt(pd.Timestamp("2021-01-15",tz="UTC")),"target_segment_h1"]="holdout"
        fc=walk_forward(d,NaiveRW,Task(1),CFG);second=fc.copy();second["model"]="other"
        second.loc[second.index[0],["rv_forecast_pct2","volatility_forecast_pct"]]=np.nan
        second.loc[second.index[0],"status"]="missing_features"
        ev,coverage=build_eval_frame(pd.concat([fc,second]),d)
        self.assertFalse(ev.origin_date.eq(fc.origin_date.iloc[0]).any())
        self.assertEqual(ev.groupby("model").size().nunique(),1)

    def test_hln_and_gap_aware_hac(self):
        rng=np.random.default_rng(7);a=rng.normal(size=200)**2;b=rng.normal(size=200)**2
        raw=dm_test(a,b,h=1,hln=False);adjusted=dm_test(a,b,h=1)
        self.assertAlmostEqual(adjusted["stat"],raw["stat"]*np.sqrt(199/200))
        self.assertAlmostEqual(adjusted["p_value"],2*stats.t.sf(abs(adjusted["stat"]),199))
        identical=dm_test(a,a);self.assertEqual(identical["status"],"degenerate_loss_difference")
        dates=pd.date_range("2021-01-01",periods=200,tz="UTC")
        mask=np.ones(200,bool);mask[70:80]=False
        sparse=dm_test(a[mask],b[mask],h=7,dates=dates[mask])
        aa=a.copy();bb=b.copy();aa[~mask]=np.nan;bb[~mask]=np.nan
        explicit=dm_test(aa,bb,h=7,dates=dates)
        self.assertAlmostEqual(sparse["stat"],explicit["stat"])
        self.assertEqual(float(qlike_loss(2.,2.)),0.)

if __name__=="__main__": unittest.main()
