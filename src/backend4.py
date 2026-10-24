"""Point-in-time VaR/ES forecasts and backtests for Backend 4."""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.data.download import save_json, sha256
from src.evaluation.validate import validate_forecasts
from src.utils.config import ROOT, load_config, protocol_hash

RISK_COLUMNS = [
    "symbol", "model", "window", "horizon_days", "confidence", "tail_probability",
    "origin_date", "target_date", "forecast_available_at", "regime", "target_segment",
    "forecast_status", "risk_method", "risk_status", "mean_forecast_pct",
    "sigma_forecast_pct", "var_loss_pct", "es_loss_pct", "return_quantile_pct",
    "es_return_pct", "realized_return_pct", "loss_pct", "breach", "n_residuals",
    "protocol_sha256", "dataset_sha256",
]


def load_risk_options(path=None):
    import tomllib

    path = Path(path) if path else ROOT / "config/backend4.toml"
    options = tomllib.loads(path.read_text(encoding="utf-8"))["risk"]
    if not options["confidence_levels"] or any(not 0 < level < 1 for level in options["confidence_levels"]):
        raise ValueError("Risk confidence levels must lie strictly between zero and one")
    if options["residual_window_calendar_days"] < 1 or options["min_fhs_residuals"] < 1:
        raise ValueError("Residual window and minimum pool size must be positive")
    if options["min_backtest_observations"] < 1:
        raise ValueError("Minimum backtest sample must be positive")
    return options


def student_t_tail(alpha, nu):
    """Return the lower-tail quantile and ES for a unit-variance Student-t."""
    if not np.isfinite(nu) or nu <= 2:
        raise ValueError("Student-t risk requires finite degrees of freedom greater than two")
    raw_quantile = float(stats.t.ppf(alpha, df=nu))
    scale = math.sqrt((nu - 2) / nu)
    quantile = scale * raw_quantile
    expected_shortfall = scale * (
        -(nu + raw_quantile**2) / (nu - 1) * stats.t.pdf(raw_quantile, df=nu) / alpha
    )
    return quantile, float(expected_shortfall)


def empirical_tail(residuals, alpha):
    values = np.asarray(residuals, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("Historical simulation requires at least one finite residual")
    quantile = float(np.quantile(values, alpha, method="linear"))
    tail = values[values <= quantile]
    return quantile, float(tail.mean())


def kupiec_test(breaches, alpha, minimum_observations=100):
    hits = np.asarray(breaches, dtype=bool)
    n = int(hits.size)
    exceptions = int(hits.sum())
    result = {"n_observations": n, "n_breaches": exceptions,
              "expected_breach_rate": float(alpha), "observed_breach_rate": exceptions / n if n else np.nan,
              "lr_uc": np.nan, "p_value_uc": np.nan, "uc_status": "insufficient_observations"}
    if n < minimum_observations:
        return result
    observed = exceptions / n
    null_ll = stats_binomial_loglik(exceptions, n, alpha)
    fitted_ll = stats_binomial_loglik(exceptions, n, observed)
    statistic = max(0.0, 2 * (fitted_ll - null_ll))
    result.update(lr_uc=statistic, p_value_uc=float(stats.chi2.sf(statistic, 1)), uc_status="ok")
    return result


def stats_binomial_loglik(successes, trials, probability):
    from scipy.special import xlogy

    return float(xlogy(successes, probability) + xlogy(trials - successes, 1 - probability))


def christoffersen_test(breaches, minimum_observations=100):
    hits = np.asarray(breaches, dtype=bool)
    result = {"n_transitions": 0, "n00": 0, "n01": 0, "n10": 0, "n11": 0,
              "lr_ind": np.nan, "p_value_ind": np.nan, "ind_status": "insufficient_observations"}
    if hits.size < 2 or hits.size < minimum_observations:
        return result
    pairs = [(bool(left), bool(right)) for left, right in zip(hits[:-1], hits[1:])]
    return christoffersen_test_from_pairs(pairs, minimum_observations)


def _forecast_residuals(forecast, dataset):
    truth = dataset[["symbol", "origin_date", "ret_d"]].rename(
        columns={"origin_date": "target_date", "ret_d": "realized_return_pct"}
    )
    selected = forecast.loc[
        forecast["horizon_days"].eq(1) & forecast["status"].eq("ok"),
        ["symbol", "model", "window", "origin_date", "target_date", "mean_forecast_pct",
         "volatility_forecast_pct"],
    ].copy()
    selected = selected.merge(truth, on=["symbol", "target_date"], how="left", validate="many_to_one")
    mean = pd.to_numeric(selected["mean_forecast_pct"], errors="coerce").fillna(0.0)
    sigma = pd.to_numeric(selected["volatility_forecast_pct"], errors="coerce")
    actual = pd.to_numeric(selected["realized_return_pct"], errors="coerce")
    selected["standardized_residual"] = (actual - mean) / sigma
    selected["observable_at"] = pd.to_datetime(selected["target_date"], utc=True) + pd.Timedelta(days=1)
    return selected.loc[
        np.isfinite(selected["standardized_residual"]) & np.isfinite(sigma) & sigma.gt(0)
    ].copy()


def _risk_for_forecast(row, residuals, options, confidence):
    alpha = 1.0 - confidence
    method = "standardized_student_t" if row["model"] in {"garch", "gjr_garch"} else "filtered_historical_simulation"
    result = {
        "risk_method": method, "risk_status": "ok", "n_residuals": 0,
        "mean_forecast_pct": np.nan, "sigma_forecast_pct": np.nan,
        "var_loss_pct": np.nan, "es_loss_pct": np.nan,
        "return_quantile_pct": np.nan, "es_return_pct": np.nan,
    }
    if row["status"] != "ok":
        result["risk_status"] = "forecast_" + str(row["status"])
        return result
    sigma = float(row["volatility_forecast_pct"])
    if not np.isfinite(sigma) or sigma <= 0:
        result["risk_status"] = "invalid_volatility_forecast"
        return result
    mean = row.get("mean_forecast_pct", np.nan)
    mean = float(mean) if pd.notna(mean) and np.isfinite(float(mean)) else 0.0
    result.update(mean_forecast_pct=mean, sigma_forecast_pct=sigma)

    if method == "standardized_student_t":
        try:
            z_quantile, z_es = student_t_tail(alpha, float(row["nu"]))
        except (KeyError, TypeError, ValueError):
            result["risk_status"] = "invalid_student_t_parameters"
            return result
    else:
        if residuals is None:
            available = np.array([], dtype=float)
        else:
            observable_dates, target_dates, values = residuals
            origin = np.datetime64(pd.Timestamp(row["origin_date"]).tz_localize(None), "ns")
            lower = origin - np.timedelta64(options["residual_window_calendar_days"] - 1, "D")
            stop = int(np.searchsorted(observable_dates, origin, side="right"))
            start = int(np.searchsorted(target_dates[:stop], lower, side="left"))
            available = values[start:stop]
        result["n_residuals"] = int(len(available))
        if len(available) < options["min_fhs_residuals"]:
            result["risk_status"] = "insufficient_residual_history"
            return result
        z_quantile, z_es = empirical_tail(available, alpha)

    return_quantile = mean + sigma * z_quantile
    es_return = mean + sigma * z_es
    result.update(return_quantile_pct=return_quantile, es_return_pct=es_return,
                  var_loss_pct=-return_quantile, es_loss_pct=-es_return)
    return result


def build_risk_forecasts(forecasts, dataset, options, confidence_levels, segment="evaluation"):
    indexed_dataset = dataset.set_index(["symbol", "origin_date"])
    if not indexed_dataset.index.is_unique:
        raise ValueError("Dataset must contain one row per symbol/origin")
    residual_lookup = {}
    for key, group in _forecast_residuals(forecasts, dataset).groupby(["symbol", "model", "window"], sort=False):
        group = group.sort_values("observable_at")
        residual_lookup[key] = (
            group["observable_at"].to_numpy(dtype="datetime64[ns]"),
            group["target_date"].to_numpy(dtype="datetime64[ns]"),
            group["standardized_residual"].to_numpy(dtype=float),
        )
    records = []
    h1 = forecasts.loc[forecasts["horizon_days"].eq(1)].copy()
    for row in h1.to_dict("records"):
        target_key = (row["symbol"], row["target_date"])
        origin_key = (row["symbol"], row["origin_date"])
        if target_key not in indexed_dataset.index or origin_key not in indexed_dataset.index:
            raise ValueError("Forecast target must map to exactly one realized daily return")
        actual = indexed_dataset.loc[target_key]
        origin = indexed_dataset.loc[origin_key]
        if actual["target_segment_h1"] != segment:
            continue
        residual_key = (row["symbol"], row["model"], row["window"])
        residual_data = residual_lookup.get(residual_key)
        for confidence in confidence_levels:
            risk = _risk_for_forecast(row, residual_data, options, confidence)
            risk_status = risk["risk_status"]
            realized = actual["ret_d"]
            if risk_status == "ok" and (not np.isfinite(realized) or pd.isna(realized)):
                risk_status = "missing_realized_return"
            threshold = risk["return_quantile_pct"]
            breach = bool(float(realized) < threshold) if risk_status == "ok" else False
            records.append({
                "symbol": row["symbol"], "model": row["model"], "window": row["window"],
                "horizon_days": 1, "confidence": float(confidence), "tail_probability": 1-confidence,
                "origin_date": row["origin_date"], "target_date": row["target_date"],
                "forecast_available_at": row["forecast_available_at"], "regime": origin["regime"],
                "target_segment": segment, "forecast_status": row["status"],
                "risk_status": risk_status, **{k: v for k, v in risk.items() if k != "risk_status"},
                "realized_return_pct": realized,
                "loss_pct": -float(realized) if pd.notna(realized) and np.isfinite(realized) else np.nan,
                "breach": breach if risk_status == "ok" else pd.NA,
                "protocol_sha256": row["protocol_sha256"], "dataset_sha256": row["dataset_sha256"],
            })
    result = pd.DataFrame.from_records(records, columns=RISK_COLUMNS)
    if result.empty:
        raise ValueError(f"No {segment} one-day forecasts were found")
    return result


def backtest_tables(risk, minimum_observations):
    valid = risk.loc[
        risk["risk_status"].eq("ok") & risk["breach"].notna()
    ].copy()
    keys = ["symbol", "model", "window", "confidence"]
    summaries, crisis_rows = [], []
    for group_key, group in risk.groupby(keys, sort=True):
        part = valid.loc[
            valid["symbol"].eq(group_key[0]) & valid["model"].eq(group_key[1])
            & valid["window"].eq(group_key[2]) & valid["confidence"].eq(group_key[3])
        ].sort_values("origin_date")
        breaches = part["breach"].astype(bool).to_numpy()
        alpha = float(group["tail_probability"].iloc[0])
        uc = kupiec_test(breaches, alpha, minimum_observations)

        # Conditional-independence transitions are computed only across adjacent calendar dates.
        if len(part) > 1:
            adjacent_pairs = []
            previous = None
            for _, current in part.iterrows():
                if previous is not None and current["origin_date"] - previous["origin_date"] == pd.Timedelta(days=1):
                    adjacent_pairs.append((bool(previous["breach"]), bool(current["breach"])))
                previous = current
            ci = christoffersen_test_from_pairs(adjacent_pairs, minimum_observations)
        else:
            ci = christoffersen_test([], minimum_observations)
        n = len(part)
        lr_cc = uc["lr_uc"] + ci["lr_ind"] if pd.notna(uc["lr_uc"]) and pd.notna(ci["lr_ind"]) else np.nan
        summaries.append({
            "symbol": group_key[0], "model": group_key[1], "window": group_key[2],
            "horizon_days": 1, "confidence": group_key[3], "tail_probability": alpha,
            "risk_method": group["risk_method"].iloc[0], "n_forecasts": n,
            "n_risk_unavailable": int(len(group) - n), "mean_var_loss_pct": part["var_loss_pct"].mean(),
            "mean_es_loss_pct": part["es_loss_pct"].mean(),
            "expected_breaches": n * alpha, "n_breaches": int(breaches.sum()) if n else 0,
            "observed_breach_rate": float(breaches.mean()) if n else np.nan,
            "lr_uc": uc["lr_uc"], "p_value_uc": uc["p_value_uc"], "uc_status": uc["uc_status"],
            **ci, "lr_cc": lr_cc,
            "p_value_cc": float(stats.chi2.sf(lr_cc, 2)) if np.isfinite(lr_cc) else np.nan,
            "cc_status": "ok" if np.isfinite(lr_cc) else "insufficient_observations",
        })
        for regime, regime_group in part.groupby("regime", dropna=False):
            crisis_rows.append({
                "symbol": group_key[0], "model": group_key[1], "window": group_key[2],
                "horizon_days": 1, "confidence": group_key[3], "regime": regime,
                "n_forecasts": len(regime_group), "n_breaches": int(regime_group["breach"].sum()),
                "breach_rate": float(regime_group["breach"].mean()),
            })
    return pd.DataFrame(summaries), pd.DataFrame(crisis_rows)


def christoffersen_test_from_pairs(pairs, minimum_observations=100):
    if not pairs:
        return christoffersen_test([], minimum_observations)
    counts = {
        "n00": sum(not left and not right for left, right in pairs),
        "n01": sum(not left and right for left, right in pairs),
        "n10": sum(left and not right for left, right in pairs),
        "n11": sum(left and right for left, right in pairs),
    }
    n = sum(counts.values())
    result = {"n_transitions": n, **counts, "lr_ind": np.nan, "p_value_ind": np.nan,
              "ind_status": "insufficient_observations"}
    if n < minimum_observations - 1:
        return result
    from scipy.special import xlogy

    total_breaches = counts["n01"] + counts["n11"]
    p = total_breaches / n
    p01 = counts["n01"] / (counts["n00"] + counts["n01"]) if counts["n00"] + counts["n01"] else 0.0
    p11 = counts["n11"] / (counts["n10"] + counts["n11"]) if counts["n10"] + counts["n11"] else 0.0
    ll_iid = float(xlogy(total_breaches, p) + xlogy(n-total_breaches, 1-p))
    ll_markov = float(xlogy(counts["n01"], p01) + xlogy(counts["n00"], 1-p01)
                      + xlogy(counts["n11"], p11) + xlogy(counts["n10"], 1-p11))
    statistic = max(0.0, 2*(ll_markov-ll_iid))
    result.update(lr_ind=statistic, p_value_ind=float(stats.chi2.sf(statistic, 1)), ind_status="ok")
    return result


def make_backtest_figures(risk, directory, confidence):
    models = sorted(risk["model"].unique())
    if not models:
        return
    columns = 3
    rows = math.ceil(len(models) / columns)
    for symbol, symbol_part in risk.loc[risk["window"].eq("rolling")].groupby("symbol"):
        fig, axes = plt.subplots(rows, columns, figsize=(15, 3.1*rows), squeeze=False, layout="constrained")
        for ax, model in zip(axes.flat, models):
            part = symbol_part.loc[
                symbol_part["model"].eq(model) & symbol_part["confidence"].eq(confidence)
                & symbol_part["risk_status"].eq("ok")
            ].sort_values("target_date")
            if part.empty:
                ax.set_visible(False)
                continue
            ax.plot(part["target_date"], part["loss_pct"], color="black", linewidth=.6, label="Realized loss")
            ax.plot(part["target_date"], part["var_loss_pct"], color="#377eb8", linewidth=.8, label="VaR")
            ax.scatter(part.loc[part["breach"].astype(bool), "target_date"],
                       part.loc[part["breach"].astype(bool), "loss_pct"],
                       color="#d62728", s=9, label="Breach", zorder=3)
            ax.set_title(model)
            ax.set_ylabel("Loss (%)")
            ax.grid(alpha=.2)
        for ax in axes.flat[len(models):]:
            ax.set_visible(False)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        if handles:
            fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
        fig.suptitle(f"{symbol} | rolling h1 | VaR {confidence:.0%} and breaches")
        fig.savefig(directory / f"backend4_{symbol}_rolling_h1_var_q{int(confidence*100)}.png", dpi=135)
        plt.close(fig)


def run(segment="evaluation"):
    if segment != "evaluation":
        raise ValueError("Backend 4 currently scores evaluation only; holdout requires a separately approved final run")
    config = load_config()
    options = load_risk_options()
    dataset_path = ROOT / "data/processed/dataset.parquet"
    meta_path = dataset_path.with_name("dataset_meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if sha256(dataset_path) != meta["dataset_sha256"] or meta["protocol_sha256"] != protocol_hash(config):
        raise ValueError("Stale dataset/protocol; rebuild upstream artifacts before Backend 4")
    dataset = pd.read_parquet(dataset_path)
    required = {"symbol", "origin_date", "ret_d", "regime", "target_segment_h1"}
    if not required.issubset(dataset.columns):
        raise ValueError(f"Dataset is missing Backend 4 columns: {sorted(required-set(dataset.columns))}")

    forecast_folder = ROOT / "outputs/forecasts"
    forecast_parts = []
    input_hashes = {}
    for path in sorted(forecast_folder.glob("*.parquet")):
        if path.stem.endswith("_risk"):
            continue
        forecast = pd.read_parquet(path)
        errors = validate_forecasts(forecast, dataset, config, meta["dataset_sha256"], path.name)
        if errors:
            raise ValueError(f"{path.name}: {errors}")
        model = str(forecast["model"].iloc[0])
        if not forecast["model"].eq(model).all() or not forecast["symbol"].eq(path.name.split("_")[0]).all():
            raise ValueError(f"Forecast identity mismatch: {path.name}")
        forecast_parts.append(forecast)
        input_hashes[path.name] = sha256(path)
    if not forecast_parts:
        raise ValueError("No upstream forecasts found; run Backend 1, 2, and 3 first")
    forecasts = pd.concat(forecast_parts, ignore_index=True)
    if forecasts.duplicated(["symbol", "model", "window", "horizon_days", "origin_date"]).any():
        raise ValueError("Duplicate model forecast keys across input files")

    risk = build_risk_forecasts(forecasts, dataset, options, options["confidence_levels"], segment)
    backtests, crisis = backtest_tables(risk, options["min_backtest_observations"])
    risk_dir = ROOT / "outputs/risk"
    tables_dir = ROOT / "outputs/tables"
    figures_dir = ROOT / "outputs/figures"
    for directory in (risk_dir, tables_dir, figures_dir):
        directory.mkdir(parents=True, exist_ok=True)
    for (symbol, model), part in risk.groupby(["symbol", "model"], sort=True):
        part.to_parquet(risk_dir / f"{symbol}_{model}_risk.parquet", index=False)
    backtests.to_csv(tables_dir / "backend4_backtesting.csv", index=False)
    crisis.to_csv(tables_dir / "backend4_crisis_breaches.csv", index=False)
    for confidence in options["confidence_levels"]:
        make_backtest_figures(risk, figures_dir, float(confidence))
    config_hash = sha256(ROOT / "config/backend4.toml")
    save_json(ROOT / "outputs/diagnostics/backend4_validation.json", {
        "status": "passed", "segment": segment, "horizon_days": 1,
        "dataset_sha256": meta["dataset_sha256"], "protocol_sha256": protocol_hash(config),
        "backend4_config_sha256": config_hash, "input_forecast_sha256": input_hashes,
        "risk_rows": len(risk), "backtest_rows": len(backtests),
        "risk_status_counts": risk["risk_status"].value_counts().to_dict(),
        "point_in_time_residual_filter": "observable_at <= forecast origin",
        "fhs_residual_window_calendar_days": options["residual_window_calendar_days"],
        "minimum_fhs_residuals": options["min_fhs_residuals"],
        "holdout_scored": False,
    })
    print(f"Backend 4: {len(risk)} VaR/ES rows; {len(backtests)} backtest summaries; evaluation only", flush=True)
    return risk, backtests, crisis


def main():
    run()


if __name__ == "__main__":
    main()
