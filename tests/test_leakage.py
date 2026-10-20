"""Test chống leakage + sanity khung đánh giá.  Chạy: `pytest tests/` hoặc `python tests/test_leakage.py`.

Ý tưởng chính: nếu feature/dự báo tại ngày T thực sự chỉ phụ thuộc thông tin <= T thì
PHÁ HỎNG (thay bằng rác) toàn bộ dữ liệu sau T không được làm chúng thay đổi.
"""
import copy
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest

from src.data.synthetic import simulate_universe
from src.evaluation.baselines import HARRV, HARRVLog, NaiveRW, HistMean
from src.evaluation.dm import dm_test
from src.evaluation.metrics import add_losses, qlike_loss, summarize
from src.evaluation.validate import validate_forecasts
from src.evaluation.walkforward import run_all_assets
from src.features.build_features import build_dataset
from src.features.schema import FEATURE_COLS, HAR_COLS, y_col, ylog_col
from src.utils.config import load_config

CFG = copy.deepcopy(load_config())
CFG["regimes"]["min_history"] = 100       # dataset test ngắn
CFG["assets"] = ["BTCUSDT"]
START, END = "2020-01-01", "2021-06-30"   # ~547 ngày
ASSET = "BTCUSDT"
T = pd.Timestamp("2020-12-10")            # ngày origin dùng để cắt/phá hỏng
CHECK = FEATURE_COLS + ["regime", "close", "n_ret"]


@lru_cache(maxsize=1)
def _raw():
    bars, macro = simulate_universe([ASSET], START, END, seed=7)
    return bars[ASSET], macro


def _build(bars, macro):
    return build_dataset({ASSET: bars}, macro, CFG).set_index("date")


@lru_cache(maxsize=1)
def _full():
    return _build(*_raw())


def _same(a, b):
    pd.testing.assert_frame_equal(a[CHECK], b[CHECK], check_exact=False, rtol=1e-12, atol=1e-12)


def test_features_unchanged_when_future_removed():
    bars, macro = _raw()
    end = T + pd.Timedelta(days=1)
    tr = _build(bars[bars["timestamp"] < end], macro[macro["date"] < end])
    _same(_full().loc[:T], tr.loc[:T])


def test_features_unchanged_when_future_corrupted():
    bars, macro = _raw()
    end = T + pd.Timedelta(days=1)
    rng = np.random.default_rng(0)
    b = bars.copy(); m = macro.copy()
    fut = b["timestamp"] >= end
    for c in ["open", "high", "low", "close", "volume", "quote_volume"]:
        b.loc[fut, c] = rng.uniform(1, 1e6, fut.sum())
    m.loc[m["date"] >= end, ["vix", "usd"]] = 1e3
    _same(_full().loc[:T], _build(b, m).loc[:T])


def test_macro_is_lagged_one_day():
    bars, macro = _raw()
    m = macro.copy()
    day = pd.Timestamp("2020-11-12")                      # thứ Năm, có trong macro
    assert day in set(m["date"])
    m.loc[m["date"] == day, "vix"] = 500.0
    new = _build(bars, m)
    full = _full()
    assert new.loc[day, "log_vix_l1"] == full.loc[day, "log_vix_l1"]            # cùng ngày: chưa thấy
    assert np.isclose(new.loc[day + pd.Timedelta(days=1), "log_vix_l1"], np.log(500.0))  # hôm sau mới thấy


def test_macro_weekend_uses_past_only():
    full = _full()
    bars, macro = _raw()
    sun = pd.Timestamp("2020-11-15")                      # Chủ nhật: dùng VIX thứ Sáu 13/11 (<= t-1)
    fri = macro.set_index("date").loc["2020-11-13", "vix"]
    assert np.isclose(full.loc[sun, "log_vix_l1"], np.log(fri))


def test_rv_and_rolling_match_bruteforce():
    bars, _ = _raw()
    full = _full()
    b = bars.set_index("timestamp")["close"]
    # tìm 1 ngày đủ 288 bar liên tục -> RV brute-force phải khớp tuyệt đối
    cnt = b.groupby(b.index.normalize()).size()
    day = next(x for x in cnt.index if x >= pd.Timestamp("2020-09-01") and cnt[x] == 288 and
               (x - pd.Timedelta(minutes=5)) in b.index)
    c = b.loc[day:day + pd.Timedelta(hours=23, minutes=55)]
    allc = pd.concat([b.loc[[day - pd.Timedelta(minutes=5)]], c])
    r = 100 * np.log(allc).diff().dropna()
    assert len(r) == 288
    assert np.isclose(full.loc[day, "rv_d"], (r ** 2).sum())
    rv = full["rv_d"]
    t = full.index.get_loc(pd.Timestamp("2020-12-01"))
    assert np.isclose(full["rv_w"].iloc[t], rv.iloc[t - 4:t + 1].mean())
    assert np.isclose(full["rv_m"].iloc[t], rv.iloc[t - 21:t + 1].mean())


def test_target_is_future_and_features_are_not():
    full = _full()
    rv = full["rv_d"]
    t = full.index.get_loc(pd.Timestamp("2020-12-01"))
    assert np.isclose(full[y_col(1)].iloc[t], rv.iloc[t + 1])
    assert np.isclose(full[y_col(7)].iloc[t], rv.iloc[t + 1:t + 8].mean())
    assert np.isclose(full[ylog_col(1)].iloc[t], np.log(rv.iloc[t + 1]))
    assert full[y_col(1)].iloc[-1] != full[y_col(1)].iloc[-1]    # NaN ở cuối mẫu: không backfill
    assert not any(c.startswith("y_") for c in FEATURE_COLS)


def test_target_at_T_depends_on_future_sanity():
    """Kiểm tra bản thân phép thử có 'răng': target tại T PHẢI đổi khi phá dữ liệu sau T."""
    bars, macro = _raw()
    end = T + pd.Timedelta(days=1)
    tr = _build(bars[bars["timestamp"] < end], macro)
    assert np.isnan(tr.loc[T, y_col(1)]) and not np.isnan(_full().loc[T, y_col(1)])


def _ds():
    return _full().reset_index()


@pytest.mark.parametrize("h", [1, 7])
def test_walkforward_ignores_future_labels_and_features(h):
    d = _ds()
    C = T
    kw = dict(scheme="expanding", min_train=120, window=None, refit_every=1, test_start="2020-08-01", test_end=None)
    base = run_all_assets(d, HARRV, h, **kw)
    base_log = run_all_assets(d, HARRVLog, h, **kw)
    d2 = d.copy()
    rng = np.random.default_rng(1)
    ycols = [y_col(k) for k in CFG["horizons"]] + [ylog_col(k) for k in CFG["horizons"]]
    # nhãn của các dòng có date > C - h chưa được biết tại origin <= C
    late = d2["date"] > C - pd.Timedelta(days=h)
    for c in ycols:
        d2.loc[late, c] = rng.uniform(1, 100, late.sum())
    # feature của các dòng sau C cũng phá hỏng
    after = d2["date"] > C
    for c in FEATURE_COLS:
        if c in d2:
            d2.loc[after, c] = rng.uniform(1, 100, after.sum())
    for f, m in ((base, HARRV), (base_log, HARRVLog)):
        new = run_all_assets(d2, m, h, **kw)
        a = f[f["origin_date"] <= C].reset_index(drop=True)
        b = new[new["origin_date"] <= C].reset_index(drop=True)
        assert len(a) > 50 and a["origin_date"].max() == C   # có origin đúng tại mốc cắt
        pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_forecast_validator_catches_leakage_and_bad_values():
    d = _ds()
    kw = dict(scheme="expanding", min_train=120, window=None, refit_every=5, test_start="2020-08-01", test_end=None)
    fc = run_all_assets(d, HARRV, 1, **kw)
    assert validate_forecasts(fc, d) == []
    bad = fc.copy(); bad["train_end"] = bad["origin_date"]            # dùng nhãn chưa biết
    assert any("LEAKAGE" in e for e in validate_forecasts(bad, d))
    bad = fc.copy(); bad.loc[0, "y_pred"] = -1.0
    assert validate_forecasts(bad, d)
    assert validate_forecasts(pd.concat([fc, fc.iloc[:1]]), d)        # trùng


def _eval(fc, d, h):
    t = d[["asset", "date", y_col(h)]].rename(columns={"date": "origin_date", y_col(h): "y_true"})
    return add_losses(fc.merge(t, on=["asset", "origin_date"]).dropna(subset=["y_true"]))


def test_framework_sanity_naive_oracle_har():
    d = _ds()
    kw = dict(scheme="expanding", min_train=120, window=None, refit_every=5, test_start="2020-08-01", test_end=None)
    naive = run_all_assets(d, NaiveRW, 1, **kw)
    m = _eval(naive, d, 1)
    rv = d.set_index("date")["rv_d"]
    assert np.allclose(naive["y_pred"].values, rv.loc[naive["origin_date"]].values)   # naive = RV_t
    # oracle: dự báo = thực tế -> loss = 0
    o = m.copy(); o["y_pred"] = o["y_true"]; o = add_losses(o)
    s = summarize(o)
    assert s["RMSE"] == 0 and s["MAE"] == 0 and abs(s["QLIKE"]) < 1e-12
    # QLIKE bất đối xứng: dự báo thấp bị phạt nặng hơn dự báo cao cùng tỷ lệ
    assert qlike_loss(1.0, 0.5) > qlike_loss(1.0, 2.0)
    # HAR phải thắng naive trên DGP có persistence + noise đo lường (khung không bị lỗi dấu/lệch pha)
    har = _eval(run_all_assets(d, HARRV, 1, **kw), d, 1)
    common = m.merge(har, on="origin_date", suffixes=("_n", "_h"))
    assert common["qlike_h"].mean() < common["qlike_n"].mean()
    assert common["se_h"].mean() < common["se_n"].mean()


def test_dm_properties():
    rng = np.random.default_rng(3)
    a = rng.normal(1, 0.3, 400) ** 2
    assert np.isnan(dm_test(a, a)["stat"])                             # forecast trùng -> không kiểm định
    r = dm_test(a + 0.3, a + rng.normal(0, 0.05, 400))
    assert r["stat"] > 3 and r["p_value"] < 0.01                        # A loss cao hơn rõ rệt
    # HLN h=1: stat = DM * sqrt((n-1)/n)
    x, y = rng.normal(size=300) ** 2, rng.normal(size=300) ** 2
    raw, adj = dm_test(x, y, 1, hln=False), dm_test(x, y, 1, hln=True)
    assert np.isclose(adj["stat"], raw["stat"] * np.sqrt(299 / 300))
    # size: dưới H0 với h=1 tỷ lệ bác bỏ 5% xấp xỉ 5%
    rej = np.mean([dm_test(rng.normal(size=250) ** 2, rng.normal(size=250) ** 2)["p_value"] < 0.05 for _ in range(400)])
    assert 0.02 < rej < 0.09
    # h=7 với d ~ MA(6): dùng lrv đa lag, size không phồng nặng
    def ma6():
        e = rng.normal(size=256)
        return np.convolve(e, np.ones(7) / 7, "valid")[:250]
    rej7 = np.mean([dm_test(ma6() + 5, np.full(250, 5.0), 7)["p_value"] < 0.05 for _ in range(400)])
    assert rej7 < 0.12


if __name__ == "__main__":
    import inspect
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        marks = getattr(fn, "pytestmark", [])
        params = [m.args[1] for m in marks if m.name == "parametrize"]
        cases = params[0] if params else [None]
        for c in cases:
            try:
                fn(c) if params else fn()
                print(f"PASS {name}" + (f"[{c}]" if params else ""))
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    sys.exit(1 if fails else 0)
