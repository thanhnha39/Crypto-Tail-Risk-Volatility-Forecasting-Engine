"""Regressions for year-boundary residual seeding, freeze integrity and final-run guards."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.risk.run import risk_forecast_input, _risk_rows
from src.final_holdout import check_frozen, sha, run
from src.evaluation.walkforward import refit_origin
from src.utils.config import load_config

def fixture():
    dates=pd.date_range('2025-11-20','2026-01-03',tz='UTC')
    rows=[]
    for w in ('rolling','expanding'):
        for i,d in enumerate(dates):
            rows.append(dict(symbol='BTCUSDT',model='har_rv',window=w,horizon_days=1,
                origin_date=d-pd.Timedelta(days=1),target_date=d,forecast_available_at=d,
                status='ok',rv_forecast_pct2=4.,volatility_forecast_pct=2.,
                mean_forecast_pct=0.,realized_return_pct=float(np.sin(i)*4)))
    frame=pd.DataFrame(rows);start=pd.Timestamp('2026-01-01',tz='UTC');end=dates[-1]
    return frame.loc[frame.target_date.ge(start)].copy(),frame.loc[frame.target_date.lt(start)].copy(),start,end

class TestHoldoutRisk(unittest.TestCase):
    def test_january_first_keeps_prior_residuals_and_excludes_own_target(self):
        current,history,start,end=fixture();scored,pool=risk_forecast_input(current,history,start,end)
        risk=_risk_rows(scored,pool);first=risk.loc[risk.date.eq(start)]
        self.assertTrue(first.status.eq('ok').all())
        self.assertTrue(first.n_fhs_residuals.eq(len(history)//2).all())
        self.assertTrue(first.last_residual_target_date.eq(start-pd.Timedelta(days=1)).all())
        self.assertTrue(risk.loc[risk.date.eq(end)].n_fhs_residuals.eq(len(history)//2+2).all())

    def test_future_returns_cannot_change_first_forecast(self):
        current,history,start,end=fixture();scored,pool=risk_forecast_input(current,history,start,end)
        before=_risk_rows(scored.loc[scored.target_date.eq(start)],pool)
        current['realized_return_pct']=-1e8
        scored,pool=risk_forecast_input(current,history,start,end)
        after=_risk_rows(scored.loc[scored.target_date.eq(start)],pool)
        np.testing.assert_array_equal(before['var'],after['var'])
        np.testing.assert_array_equal(before.es,after.es)

    def test_historical_and_holdout_overlap_is_rejected(self):
        current,history,start,end=fixture()
        with self.assertRaises(ValueError):risk_forecast_input(current,pd.concat([history,current.head(1)]),start,end)

    def test_missing_calendar_is_rejected_not_silently_dropped(self):
        current,history,start,end=fixture()
        with self.assertRaises(ValueError):risk_forecast_input(current.iloc[1:],history,start,end)

    def test_evaluation_does_not_import_future_residuals(self):
        current,history,start,end=fixture()
        lo,hi=history.target_date.min(),history.target_date.max()
        scored,pool=risk_forecast_input(pd.concat([history,current]),None,lo,hi)
        self.assertEqual(scored.target_date.max(),hi)
        self.assertLess(pool.target_date.max(),start)

    def test_refit_clock_is_continued_across_year(self):
        cfg=load_config();origin=pd.Timestamp('2025-12-31',tz='UTC')
        anchor=pd.Timestamp('2020-12-31',tz='UTC')
        self.assertEqual((refit_origin(origin,cfg)-anchor).days%5,0)
        self.assertNotEqual(refit_origin(origin,cfg),origin)

class TestFreeze(unittest.TestCase):
    def test_changed_frozen_input_fails(self):
        with patch('pathlib.Path.is_file',return_value=True),patch('src.final_holdout.sha',return_value='original'):
            check_frozen({'file':'original'},Path('.'))
        with patch('pathlib.Path.is_file',return_value=True),patch('src.final_holdout.sha',return_value='changed'):
            with self.assertRaises(ValueError):check_frozen({'file':'original'},Path('.'))

    def test_completed_run_cannot_be_reopened(self):
        from unittest.mock import Mock
        plan=Mock();plan.exists.return_value=True;plan.read_text.return_value=json.dumps({'frozen_sha256':{}})
        state=Mock();state.exists.return_value=True;state.read_text.return_value=json.dumps({'state':'completed'})
        with patch('src.final_holdout.PLAN',plan),patch('src.final_holdout.RUN',state):
            with self.assertRaises(ValueError):run(resume=True)

if __name__=='__main__':unittest.main()
