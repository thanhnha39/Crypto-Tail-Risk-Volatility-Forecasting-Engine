"""python -m src.evaluation.aggregate
Đọc MỌI file trong outputs/forecasts/, validate, ghép y_true từ dataset, lấy mẫu chung
(origin mà mọi mô hình đều có) rồi xuất bảng + hình.

Bảng (outputs/tables):  model_comparison.csv | dm_vs_benchmark.csv | regime_performance.csv | regime_counts.csv
Hình (outputs/figures): forecast_vs_actual_*.png | rolling_qlike_*.png | regime_qlike_ratio_*.png
"""
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.evaluation.dm import dm_test, stars
from src.evaluation.metrics import add_losses, summarize
from src.evaluation.validate import truth_table, validate_forecasts
from src.utils.config import load_config, ROOT
from src.utils.io import read_table

REGIMES = ["normal", "bull", "bear", "crisis"]


def load_all_forecasts(fc_dir, dataset):
    files = sorted(set(re.sub(r"\.csv\.gz$", ".parquet", p.name) for p in fc_dir.glob("*.parquet")) |
                   set(re.sub(r"\.csv\.gz$", ".parquet", p.name) for p in fc_dir.glob("*.csv.gz")))
    parts, errors = [], []
    for f in files:
        df = read_table(fc_dir / f)
        e = validate_forecasts(df, dataset, f)
        errors += e
        if not e:
            parts.append(df)
    if errors:
        raise ValueError("File dự báo không hợp lệ:\n  " + "\n  ".join(errors))
    return pd.concat(parts, ignore_index=True)


def build_eval_frame(fc, dataset):
    """Ghép y_true/regime từ dataset; chỉ giữ origin có y_true và chung cho mọi model (theo asset, horizon)."""
    tt = truth_table(dataset, sorted(fc["horizon"].unique()))
    m = fc[["asset", "model", "horizon", "origin_date", "target_date", "y_pred"]].merge(
        tt, on=["asset", "origin_date", "horizon"], how="left").dropna(subset=["y_true"])
    n_models = m.groupby(["asset", "horizon"])["model"].transform("nunique")
    cnt = m.groupby(["asset", "horizon", "origin_date"])["model"].transform("nunique")
    m = m[cnt == n_models]
    return add_losses(m).sort_values(["asset", "horizon", "model", "origin_date"]).reset_index(drop=True)


def comparison_table(ev, benchmark):
    rows = []
    for (a, h, mdl), g in ev.groupby(["asset", "horizon", "model"]):
        rows.append({"asset": a, "horizon": h, "model": mdl, **summarize(g)})
    t = pd.DataFrame(rows)
    b = t[t["model"] == benchmark].set_index(["asset", "horizon"])
    for k in ("RMSE", "MAE", "QLIKE"):
        t[f"{k}_rel"] = t.apply(lambda r: r[k] / b.loc[(r["asset"], r["horizon"]), k], axis=1)
    return t


def _dm_rows(g_ev, benchmark, h, keys, min_n=10):
    piv = {k: g_ev.pivot(index="origin_date", columns="model", values=k) for k in ("qlike", "se", "ae")}
    out = []
    for mdl in piv["qlike"].columns:
        if mdl == benchmark:
            continue
        r = dict(keys, model=mdl)
        for k in ("qlike", "se", "ae"):
            res = dm_test(piv[k][mdl].values, piv[k][benchmark].values, h=h) if len(piv[k]) >= min_n else {}
            r[f"DM_{k}"], r[f"p_{k}"] = res.get("stat", np.nan), res.get("p_value", np.nan)
            r[f"sig_{k}"] = stars(r[f"p_{k}"])
        r["n"] = len(piv["qlike"])
        out.append(r)
    return out


def dm_table(ev, benchmark):
    rows = []
    for (a, h), g in ev.groupby(["asset", "horizon"]):
        rows += _dm_rows(g, benchmark, h, {"asset": a, "horizon": h})
    return pd.DataFrame(rows)       # DM < 0  => model có loss THẤP hơn benchmark


def regime_tables(ev, benchmark, min_n_dm):
    rows, dm_rows = [], []
    for (a, h, reg), g in ev.groupby(["asset", "horizon", "regime"]):
        for mdl, gm in g.groupby("model"):
            rows.append({"asset": a, "horizon": h, "regime": reg, "model": mdl, **summarize(gm)})
        if g["origin_date"].nunique() >= min_n_dm:
            dm_rows += _dm_rows(g, benchmark, h, {"asset": a, "horizon": h, "regime": reg}, min_n_dm)
    t = pd.DataFrame(rows)
    b = t[t["model"] == benchmark].set_index(["asset", "horizon", "regime"])
    t["QLIKE_rel"] = t.apply(lambda r: r["QLIKE"] / b.loc[(r["asset"], r["horizon"], r["regime"]), "QLIKE"], axis=1)
    dm = pd.DataFrame(dm_rows)
    if len(dm):
        t = t.merge(dm[["asset", "horizon", "regime", "model", "DM_qlike", "p_qlike", "sig_qlike"]],
                    on=["asset", "horizon", "regime", "model"], how="left")
    return t


def fig_forecast_vs_actual(ev, a, h, models, path, zoom_days=180):
    """Panel trên: toàn mẫu OOS (không vẽ naive cho đỡ rối). Panel dưới: zoom `zoom_days` ngày cuối, đủ mô hình."""
    g = ev[(ev.asset == a) & (ev.horizon == h)]
    act = g[g.model == models[0]].set_index("origin_date")["y_true"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    for ax, lo, ms in ((axes[0], act.index.min(), [m for m in models if m != "naive_rw"]),
                       (axes[1], act.index.max() - pd.Timedelta(days=zoom_days), models)):
        ax.plot(act.loc[lo:].index, np.sqrt(act.loc[lo:]), color="0.75", lw=1.6 if ax is axes[0] else 2.2, label="Thực tế (√RV)", zorder=1)
        for m in ms:
            s = g[g.model == m].set_index("origin_date")["y_pred"].loc[lo:]
            ax.plot(s.index, np.sqrt(s), lw=0.9, label=m, zorder=2)
        ax.set_yscale("log"); ax.set_ylabel("Biến động ngày (%), log")
        ax.legend(ncol=5, fontsize=8, loc="upper right")
    axes[0].set_title(f"{a}: dự báo vs thực tế, horizon {h} ngày (toàn mẫu out-of-sample)")
    axes[1].set_title(f"Zoom {zoom_days} ngày cuối")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def fig_rolling_qlike(ev, a, h, models, win, path):
    g = ev[(ev.asset == a) & (ev.horizon == h) & ev.model.isin(models)]
    p = g.pivot(index="origin_date", columns="model", values="qlike").rolling(win).mean()
    ax = p.plot(figsize=(11, 4), lw=1)
    ax.set_ylabel(f"QLIKE trung bình trượt {win} ngày"); ax.set_title(f"{a}: rolling QLIKE (h={h})")
    ax.figure.tight_layout(); ax.figure.savefig(path, dpi=130); plt.close(ax.figure)


def fig_regime_ratio(rt, a, h, benchmark, path):
    g = rt[(rt.asset == a) & (rt.horizon == h) & (rt.regime.isin(REGIMES)) & (rt.model != benchmark)]
    if g.empty:
        return
    p = g.pivot(index="regime", columns="model", values="QLIKE_rel").reindex(REGIMES)
    ax = p.plot.bar(figsize=(8, 4), rot=0)
    ax.axhline(1, color="k", lw=0.8); ax.set_ylabel(f"QLIKE / QLIKE({benchmark})")
    ax.set_title(f"{a}: QLIKE tương đối theo regime (<1 = tốt hơn benchmark), h={h}")
    ax.figure.tight_layout(); ax.figure.savefig(path, dpi=130); plt.close(ax.figure)


def main():
    cfg = load_config()
    ev_cfg = cfg["evaluation"]
    bench = ev_cfg["benchmark"]
    ds = read_table(ROOT / "data/processed/dataset.parquet")
    fc = load_all_forecasts(ROOT / "outputs/forecasts", ds)
    ev = build_eval_frame(fc, ds)
    tdir, fdir = ROOT / "outputs/tables", ROOT / "outputs/figures"
    tdir.mkdir(parents=True, exist_ok=True); fdir.mkdir(parents=True, exist_ok=True)

    comp = comparison_table(ev, bench)
    dm = dm_table(ev, bench)
    reg = regime_tables(ev, bench, ev_cfg["min_n_dm"])
    cnt = ev.drop_duplicates(["asset", "horizon", "origin_date"]).groupby(["asset", "horizon", "regime"]).size().rename("n_days").reset_index()
    for name, t in (("model_comparison", comp), ("dm_vs_benchmark", dm), ("regime_performance", reg), ("regime_counts", cnt)):
        t.to_csv(tdir / f"{name}.csv", index=False)

    others = [m for m in comp.model.unique() if m not in (bench, "naive_rw", "hist_mean")]
    show = ["naive_rw", bench] + others
    for a in cfg["assets"]:
        for h in cfg["horizons"]:
            fig_forecast_vs_actual(ev, a, h, show, fdir / f"forecast_vs_actual_{a}_h{h}.png")
            fig_rolling_qlike(ev, a, h, show, ev_cfg["rolling_qlike_window"], fdir / f"rolling_qlike_{a}_h{h}.png")
            fig_regime_ratio(reg, a, h, bench, fdir / f"regime_qlike_ratio_{a}_h{h}.png")
    print(comp.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
