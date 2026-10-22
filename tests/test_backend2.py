"""Backend 2 analytical/state/combination checks; simulated returns here are tests only."""
from functools import lru_cache
from unittest.mock import patch,Mock
import unittest
import numpy as np
import pandas as pd
from arch import arch_model
from src.models.garch import StudentTGARCH,StudentTGJR,variance_path,forecast_filter_state
from src.models.combine import combine_forecasts
from src.evaluation.walkforward import Task,ModelFitError,ModelForecastError,walk_forward
from src.evaluation.baselines import NaiveRW
from src.utils.config import load_config

def returns_fixture():
    rng=np.random.default_rng(42);n=737;variance=4.;last=0.;values=[]
    for _ in range(n):
        variance=.05+(.08+.08*(last<0))*last**2+.86*variance
        last=np.sqrt(variance)*rng.standard_t(8)*np.sqrt(6/8)
        values.append(.03+last)
    return pd.DataFrame({"symbol":"BTCUSDT","origin_date":pd.date_range("2019-01-02",periods=n,tz="UTC"),"ret_d":values})

@lru_cache(maxsize=1)
def shared_cache():return {}

def fitted(cls=StudentTGARCH,cache=None):
    train=returns_fixture().iloc[:730].copy();model=cls(cache=shared_cache() if cache is None else cache)
    model.set_context({"symbol":"BTCUSDT","window":"rolling","refit_origin":train.origin_date.iloc[-1],"train_start":train.origin_date.iloc[0]})
    model.fit(train,Task(1));return model,train

class Backend2Tests(unittest.TestCase):
    def test_near_unit_beta_uses_forecast_backcast_not_optimizer_backcast(self):
        data=returns_fixture().iloc[:730]
        fixed=arch_model(data.ret_d,mean="Constant",p=1,q=1,dist="t",rescale=False).fix(
            np.asarray([.5,.0001,0.,.9987,5.]))
        variance,residual=forecast_filter_state(fixed)
        actual=variance_path(fixed.params.to_dict(),variance,residual,7)
        reference=fixed.forecast(horizon=7,reindex=False).variance.to_numpy()[-1]
        np.testing.assert_allclose(actual,reference,rtol=1e-10,atol=1e-10)
        old=variance_path(fixed.params.to_dict(),fixed.conditional_volatility.iloc[-1]**2,residual,7)
        self.assertGreater(float(np.max(np.abs(old-reference))),1e-5)

    def test_fit_and_multistep_recursion_match_arch(self):
        for cls in [StudentTGARCH,StudentTGJR]:
            model,train=fitted(cls)
            self.assertEqual(model.fit_record["diagnostic"]["convergence_flag"],0)
            self.assertEqual(model.fit_record["diagnostic"]["arch_rescale"],1.)
            self.assertLess(model.fit_record["diagnostic"]["max_arch_forecast_difference"],1e-7)
            test=train.tail(1)
            one=model.predict(test,Task(1),history=train)[0]
            model2,_=fitted(cls);seven=model2.predict(test,Task(7),history=train)[0]
            self.assertAlmostEqual(seven,sum(model2.path))
            self.assertAlmostEqual(one,model2.path[0])
            self.assertGreater(model.params["nu"],2)

    def test_between_refit_state_matches_library_fixed_parameters(self):
        for cls in [StudentTGARCH,StudentTGJR]:
            model,train=fitted(cls);history=returns_fixture().iloc[:733].copy()
            prediction=model.predict(history.tail(1),Task(7),history=history)[0]
            reference=arch_model(pd.Series(history.ret_d.to_numpy(),index=history.origin_date),mean="Constant",p=1,o=cls.asymmetry,q=1,
                dist="t",rescale=False).fix(np.asarray(list(model.params.values())))
            path=reference.forecast(horizon=7,reindex=False).variance.to_numpy()[-1]
            np.testing.assert_allclose(model.path,path,rtol=1e-9,atol=1e-9)
            self.assertAlmostEqual(prediction,path.sum())

    def test_future_return_corruption_does_not_change_origin_forecast(self):
        first,train=fitted();history=returns_fixture();origin=history.iloc[[732]]
        expected=first.predict(origin,Task(1),history=history)
        changed=history.copy();changed.loc[changed.origin_date.gt(origin.origin_date.iloc[0]),"ret_d"]=1e6
        other,_=fitted();actual=other.predict(origin,Task(1),history=changed)
        np.testing.assert_array_equal(expected,actual)

    def test_missing_return_state_is_not_filled(self):
        model,_=fitted();history=returns_fixture().iloc[:733].copy();history.loc[730,"ret_d"]=np.nan
        with self.assertRaises(ModelForecastError):model.predict(history.tail(1),Task(1),history=history)

    def test_fit_rejects_compressed_missing_calendar(self):
        data=returns_fixture().iloc[:730].drop(index=600)
        with self.assertRaises(ModelFitError):StudentTGARCH().fit(data,Task(1))

    def test_horizon_cache_is_reused_without_reusing_mutated_state(self):
        cache={};model,train=fitted(cache=cache)
        expected=model.predict(train.tail(1),Task(7),history=train)[0]
        model.predict(returns_fixture().iloc[[732]],Task(1),history=returns_fixture())
        other=StudentTGARCH(cache=cache);other.fit(train,Task(7))
        actual=other.predict(train.tail(1),Task(7),history=train)[0]
        self.assertEqual(len(cache),1);self.assertEqual(expected,actual)

    def test_student_t_risk_scale_is_standardized_and_h7_not_exact_t(self):
        model,train=fitted();model.predict(train.tail(1),Task(1),history=train)
        details=model.forecast_metadata(Task(1));nu=details["nu"];sigma=np.sqrt(model.path[0])
        self.assertAlmostEqual(details["student_t_scale_pct"]**2*nu/(nu-2),sigma**2)
        self.assertEqual(details["innovation_distribution"],"standardized_student_t")
        self.assertTrue(np.isnan(model.forecast_metadata(Task(7))["student_t_scale_pct"]))

    def test_nonconvergence_is_recorded_and_rejected(self):
        diagnostics=[];fake=Mock();fake.convergence_flag=9;fake.optimization_result.message="test optimizer failure"
        fake.params=pd.Series({"mu":0.,"omega":.1,"alpha[1]":.1,"beta[1]":.8,"nu":8.})
        wrapper=Mock();wrapper.fit.return_value=fake
        cache={}
        with patch("src.models.garch.arch_model",return_value=wrapper):
            with self.assertRaises(ModelFitError):StudentTGARCH(cache=cache,diagnostics=diagnostics).fit(returns_fixture().iloc[:730],Task(1))
            with self.assertRaises(ModelFitError):StudentTGARCH(cache=cache,diagnostics=diagnostics).fit(returns_fixture().iloc[:730],Task(7))
        self.assertEqual(diagnostics[-1]["fit_status"],"failed")
        self.assertEqual(len(diagnostics),1)
        self.assertEqual(wrapper.fit.call_count,2)

    def test_fit_does_not_receive_other_horizon_unknown_labels(self):
        from test_leakage import dataset
        class Inspect(NaiveRW):
            def fit(self,train,task):
                assert not any(col.startswith(("y_","target_")) and not col.endswith(f"h{task.horizon}") for col in train)
                return self
        data=dataset().copy();data.loc[data.origin_date.gt(pd.Timestamp("2021-01-05",tz="UTC")),"target_segment_h1"]="out_of_scope"
        self.assertGreater(len(walk_forward(data,Inspect,Task(1),load_config())),0)

    def test_walkforward_records_fit_failure_without_fake_prediction(self):
        from test_leakage import dataset
        class Failed(NaiveRW):
            def fit(self,train,task):raise ModelFitError("test failure")
        data=dataset().copy();data.loc[data.origin_date.gt(pd.Timestamp("2021-01-05",tz="UTC")),"target_segment_h1"]="out_of_scope"
        output=walk_forward(data,Failed,Task(1),load_config())
        self.assertTrue(output.status.eq("fit_failed").all());self.assertTrue(output.rv_forecast_pct2.isna().all())

    def combination_frames(self):
        origin=pd.Timestamp("2021-01-05",tz="UTC");frames={}
        for model,value in zip(["har_rv","garch","gjr_garch"],[1.,4.,9.]):
            frames[model]=pd.DataFrame([{"symbol":"BTCUSDT","model":model,"horizon_days":1,"window":"rolling",
                "origin_date":origin,"target_start":origin+pd.Timedelta(days=1),"target_date":origin+pd.Timedelta(days=1),
                "forecast_available_at":origin+pd.Timedelta(days=1),"refit_origin":origin,"train_start":origin-pd.Timedelta(days=729),
                "train_end":origin,"train_feature_end":origin-pd.Timedelta(days=1),"n_train":700,"training_kind":"observations",
                "rv_forecast_pct2":value,"volatility_forecast_pct":np.sqrt(value),"status":"ok",
                "protocol_sha256":"same","dataset_sha256":"same","mean_forecast_pct":0.}])
        return frames

    def test_combination_averages_variance_not_sigma(self):
        frames=self.combination_frames();result=combine_forecasts(frames,list(frames))
        self.assertAlmostEqual(result.rv_forecast_pct2.iloc[0],14/3)
        self.assertAlmostEqual(result.volatility_forecast_pct.iloc[0],np.sqrt(14/3))
        self.assertNotAlmostEqual(result.volatility_forecast_pct.iloc[0],2.)

    def test_combination_requires_all_components_and_consistent_provenance(self):
        frames=self.combination_frames();frames["garch"].loc[0,"status"]="fit_failed"
        output=combine_forecasts(frames,list(frames))
        self.assertEqual(output.status.iloc[0],"component_unavailable");self.assertTrue(output.rv_forecast_pct2.isna().all())
        frames["garch"].loc[0,"dataset_sha256"]="other"
        with self.assertRaises(ValueError):combine_forecasts(frames,list(frames))
        frames=self.combination_frames()
        with self.assertRaises(ValueError):combine_forecasts(frames,list(frames),weights={key:1. for key in frames})

if __name__=="__main__":unittest.main()
