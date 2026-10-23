"""Regression tests for timing, calendar gaps, shared samples and portfolio accounting."""
import unittest
import numpy as np
import pandas as pd
from src.risk.run import _risk_rows, comparison_tables
from src.risk.metrics import christoffersen_test, value_at_risk
from src.risk.strategy import _max_drawdown, run_strategy

def example():
    target=pd.Timestamp('2021-02-01',tz='UTC')
    fc=pd.DataFrame([dict(symbol='BTCUSDT',model='har_rv',window='rolling',status='ok',
        origin_date=target-pd.Timedelta(days=1),target_date=target,forecast_available_at=target,
        rv_forecast_pct2=4.,volatility_forecast_pct=2.,mean_forecast_pct=0.)])
    dates=pd.date_range('2021-01-01',periods=40,tz='UTC')
    residuals=pd.DataFrame(dict(symbol='BTCUSDT',model='har_rv',window='rolling',
        target_date=dates,observable_at=dates+pd.Timedelta(days=1),standardized_residual=np.linspace(-3,3,40)))
    return fc,residuals

class TestPointInTimePipeline(unittest.TestCase):
    def test_future_values_do_not_change_past_risk(self):
        fc,r=example();before=_risk_rows(fc,r)
        future=r.observable_at.gt(fc.forecast_available_at.iloc[0]);r.loc[future,'standardized_residual']=-1000
        after=_risk_rows(fc,r)
        np.testing.assert_array_equal(before['var'],after['var'])
        np.testing.assert_array_equal(before.es,after.es)
        self.assertEqual(int(before.n_fhs_residuals.iloc[0]),31)

    def test_timestamp_microseconds_and_nanoseconds_identical(self):
        fc,r=example();expected=_risk_rows(fc,r)
        for c in ('target_date','observable_at'):r[c]=r[c].astype('datetime64[us, UTC]')
        actual=_risk_rows(fc,r)
        np.testing.assert_array_equal(expected['var'],actual['var'])
        np.testing.assert_array_equal(expected.n_fhs_residuals,actual.n_fhs_residuals)

    def test_late_observability_excludes_old_target(self):
        fc,r=example();r.loc[:4,'observable_at']=pd.Timestamp('2022-01-01',tz='UTC')
        result=_risk_rows(fc,r)
        self.assertEqual(int(result.n_fhs_residuals.iloc[0]),26)
        self.assertTrue((result.last_residual_observable_at<=result.forecast_available_at).all())

    def test_own_target_is_never_in_pool(self):
        fc,r=example();r.loc[r.target_date.eq(fc.target_date.iloc[0]),'standardized_residual']=-100000
        result=_risk_rows(fc,r)
        self.assertGreater(result['var'].min(),-100)

    def test_insufficient_history_has_status_not_zero_risk(self):
        fc,r=example();result=_risk_rows(fc,r.head(19))
        self.assertEqual(len(result),2)
        self.assertTrue(result.status.eq('insufficient_fhs_history').all())
        self.assertTrue(result['var'].isna().all())

    def test_duplicate_residual_rejected(self):
        fc,r=example()
        with self.assertRaises(ValueError):_risk_rows(fc,pd.concat([r,r.head(1)]))

    def test_impossible_observability_rejected(self):
        fc,r=example();r.loc[0,'observable_at']=r.target_date.iloc[0]
        with self.assertRaises(ValueError):_risk_rows(fc,r)

    def test_failed_forecast_is_preserved(self):
        fc,r=example();fc['status']='missing_features';fc['rv_forecast_pct2']=np.nan
        result=_risk_rows(fc,r)
        self.assertTrue(result.status.eq('source_forecast_unavailable').all())
        self.assertTrue(result['var'].isna().all())

class TestCalendarAndComparison(unittest.TestCase):
    def test_gap_is_not_a_transition(self):
        d=pd.to_datetime(['2021-01-01','2021-01-02','2021-01-04','2021-01-05'],utc=True)
        x=christoffersen_test([0,1,1,0],.05,dates=d)
        self.assertEqual((x['n00'],x['n01'],x['n10'],x['n11']),(0,1,1,0))
        self.assertEqual(x['n_adjacent_pairs'],2);self.assertEqual(x['n_gaps'],1)

    def test_no_state_variation_has_no_false_pass(self):
        x=christoffersen_test([0,0,0],.05)
        self.assertTrue(np.isnan(x['p_value']))
        self.assertEqual(x['status'],'insufficient_transitions')

    def test_common_sample_intersection_and_coverage(self):
        dates=pd.date_range('2021-01-01',periods=4,tz='UTC')
        rows=[]
        for model in ('a','b'):
            for i,date in enumerate(dates):
                good=not (model=='b' and i==0)
                rows.append(dict(coin='BTCUSDT',window='rolling',alpha=.05,model=model,date=date,
                    score_valid=good,status='ok' if good else 'insufficient_fhs_history',method='fhs',
                    breach=float(i%2) if good else np.nan,**{'return':-1.,'var':-2.,'es':-3.}))
        risk=pd.DataFrame(rows)
        primary,available,coverage=comparison_tables(risk,models=('a','b'))
        self.assertEqual(primary.n.tolist(),[3,3]);self.assertEqual(available.n.tolist(),[4,3])
        self.assertTrue(coverage.n_common.eq(3).all())

class TestPortfolioAccounting(unittest.TestCase):
    def test_target_day_forecast_has_no_extra_lag(self):
        d=pd.date_range('2021-01-01',periods=2)
        x=run_strategy(d,[0.,10.],[10.,1.],vol_target_annual_pct=np.sqrt(365),fee_bps=0)
        self.assertAlmostEqual(x.weight.iloc[1],1.)
        self.assertAlmostEqual(x.strategy_return.iloc[1],100*np.expm1(.1))

    def test_costs_include_initial_trade_and_drift(self):
        x=run_strategy(pd.date_range('2021-01-01',periods=2),[10.,0.],[2.,2.],
            vol_target_annual_pct=np.sqrt(365),fee_bps=5.)
        self.assertGreater(x.cost_pct.iloc[0],0)
        self.assertGreater(x.cost_pct.iloc[1],0) # sell the drift above fixed .5 weight
        self.assertLess(x.bh_return.iloc[0],100*np.expm1(.1))

    def test_compounding_recovers_buy_and_hold_without_fee(self):
        x=run_strategy(pd.date_range('2021-01-01',periods=2),[10.,-5.],[1.,1.],
            vol_target_annual_pct=np.sqrt(365),fee_bps=0)
        self.assertAlmostEqual(x.strategy_cum.iloc[-1],100*np.expm1(.05))
        self.assertAlmostEqual(x.strategy_cum.iloc[-1],x.bh_cum.iloc[-1])

    def test_initial_loss_is_in_drawdown(self):
        self.assertAlmostEqual(_max_drawdown([-10.,-5.]),-10.)

    def test_full_allocation_matches_buy_and_hold_with_same_fees(self):
        x=run_strategy(pd.date_range('2021-01-01',periods=2),[10.,-5.],[1.,1.],
            vol_target_annual_pct=np.sqrt(365),fee_bps=5.)
        np.testing.assert_allclose(x.strategy_cum,x.bh_cum,rtol=0,atol=1e-10)

    def test_missing_forecast_holds_position_without_cost(self):
        x=run_strategy(pd.date_range('2021-01-01',periods=3),[10.,5.,0.],[2.,np.nan,2.])
        self.assertEqual(len(x),3);self.assertFalse(x.forecast_used.iloc[1])
        self.assertAlmostEqual(x.cost_pct.iloc[1],0.)
        self.assertAlmostEqual(x.weight.iloc[1],x.pretrade_weight.iloc[1])

    def test_missing_calendar_or_return_rejected(self):
        with self.assertRaises(ValueError):run_strategy(['2021-01-01','2021-01-03'],[0.,1.],[1.,1.])
        with self.assertRaises(ValueError):run_strategy(pd.date_range('2021-01-01',periods=2),[0.,np.nan],[1.,1.])

    def test_nonfinite_student_t_parameter_rejected(self):
        with self.assertRaises(ValueError):value_at_risk(0,1,.05,'student_t',nu=np.nan)

if __name__=='__main__':unittest.main()
