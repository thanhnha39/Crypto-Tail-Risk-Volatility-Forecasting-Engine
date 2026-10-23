"""Summarize existing evaluation forecasts; pair window comparisons on identical dates."""
import json
import numpy as np
import pandas as pd
from src.data.download import sha256, save_json
from src.evaluation.aggregate import load_all_forecasts, build_eval_frame
from src.evaluation.dm import dm_test
from src.evaluation.metrics import summarize
from src.utils.config import ROOT, load_config, protocol_hash


def robustness_table(evaluation, config):
    records = []
    for (symbol, horizon), part in evaluation.groupby(["symbol", "horizon_days"]):
        models = sorted(part.model.unique())
        required = {(model, window) for model in models for window in ["rolling", "expanding"]}
        if set(zip(part.model, part.window)) != required:
            raise ValueError("Both windows are required for every model")
        counts = part.groupby("origin_date").size()
        dates = counts.index[counts.eq(len(required))]
        sample = part.loc[part.origin_date.isin(dates)]
        if sample.empty or sample.duplicated(["origin_date", "model", "window"]).any():
            raise ValueError("No valid unique paired window sample")
        for model in models:
            pair = sample.loc[sample.model.eq(model)]
            rolling = pair.loc[pair.window.eq("rolling")].set_index("origin_date").sort_index()
            expanding = pair.loc[pair.window.eq("expanding")].set_index("origin_date").sort_index()
            pd.testing.assert_index_equal(rolling.index, expanding.index)
            np.testing.assert_allclose(rolling.y_true, expanding.y_true)
            dm = dm_test(expanding.qlike, rolling.qlike, h=int(horizon), dates=rolling.index,
                min_n=config["backend1"]["evaluation"]["dm_min_observations"])
            base = summarize(rolling)
            for window, rows in [("rolling", rolling), ("expanding", expanding)]:
                scores = summarize(rows)
                records.append(dict(symbol=symbol, model=model, horizon_days=int(horizon),
                    window=window, role="main" if horizon == 1 and window == "rolling" else "sensitivity",
                    **scores.to_dict(), QLIKE_minus_rolling_same_horizon=float(scores.QLIKE-base.QLIKE),
                    dm_vs_rolling_stat=dm["stat"] if window == "expanding" else np.nan,
                    dm_vs_rolling_p_value=dm["p_value"] if window == "expanding" else np.nan,
                    dm_status=dm["status"] if window == "expanding" else "reference",
                    origin_start=str(rows.index.min()), origin_end=str(rows.index.max()),
                    sample="common_models_and_windows_within_symbol_horizon",
                    target="sum_daily_RV_pct2", refit_every_calendar_days=5,
                    rolling_window_calendar_days=730 if window == "rolling" else np.nan))
    return pd.DataFrame(records)


def main():
    config = load_config()
    dataset_path = ROOT/"data/processed/dataset.parquet"
    meta = json.loads(dataset_path.with_name("dataset_meta.json").read_text(encoding="utf-8"))
    if sha256(dataset_path) != meta["dataset_sha256"] or protocol_hash(config) != meta["protocol_sha256"]:
        raise ValueError("Stale dataset/protocol")
    dataset = pd.read_parquet(dataset_path)
    forecasts = load_all_forecasts(ROOT/"outputs/forecasts", dataset, config, meta["dataset_sha256"])
    evaluation, _ = build_eval_frame(forecasts, dataset, "evaluation")
    table = robustness_table(evaluation, config)
    output = ROOT/"outputs/tables/robustness.csv"
    table.to_csv(output, index=False)
    save_json(output.with_suffix(".json"), dict(status="passed", segment="evaluation", rows=len(table),
        dataset_sha256=meta["dataset_sha256"], protocol_sha256=meta["protocol_sha256"],
        input_forecast_sha256={p.name: sha256(p) for p in sorted((ROOT/"outputs/forecasts").glob("*.parquet"))},
        compared_windows=["rolling", "expanding"], horizons=[1, 7],
        window_comparisons_use_identical_dates=True, cross_horizon_loss_difference_computed=False,
        holdout_scored=False, numerical_result_used_for_retuning=False))
    print(f"Robustness: {len(table)} rows; evaluation only; paired dates within each horizon", flush=True)


if __name__ == "__main__":
    main()
