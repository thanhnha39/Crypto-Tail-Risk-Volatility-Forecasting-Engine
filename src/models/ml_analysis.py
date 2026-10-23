"""Matched volume ablation, native TreeSHAP plots and Backend 3 artifact checks."""
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.data.download import sha256, save_json
from src.evaluation.dm import dm_test
from src.evaluation.metrics import qlike_loss
from src.evaluation.validate import validate_forecasts
from src.models.ml_common import load_ml_config, ml_config_hash
from src.models.tune_ml import LOCK, warmup_fingerprint
from src.models.run_ml import locations
from src.utils.config import ROOT, load_config, protocol_hash

GROUP = ["symbol", "window", "horizon_days"]
KEY = GROUP + ["origin_date"]


def volume_ablation(dataset, frames, config, segment="evaluation"):
    records = []
    for name in ["enet", "xgboost"]:
        full, core = frames[name], frames[name+"_core"]
        paired = full.merge(core, on=KEY, suffixes=("_full", "_core"), validate="one_to_one", how="outer")
        for col in ["n_train", "train_start", "train_end", "train_feature_end", "refit_origin"]:
            left, right = paired[col+"_full"], paired[col+"_core"]
            if not (left.eq(right) | (left.isna() & right.isna())).all():
                raise ValueError("Ablation samples differ: "+col)
        # Estimation failures can differ by feature set. The paired loss sample
        # below requires both forecasts to succeed; training eligibility is
        # verified separately using the recorded training-row hashes.
        for horizon, part in paired.groupby("horizon_days"):
            truth = dataset[["symbol", "origin_date", f"y_rv_h{horizon}", f"target_segment_h{horizon}"]]
            truth = truth.rename(columns={f"y_rv_h{horizon}": "y_true", f"target_segment_h{horizon}": "segment"})
            part = part.merge(truth, on=["symbol", "origin_date"], validate="many_to_one")
            part = part.loc[part.segment.eq(segment) & part.status_full.eq("ok") & part.status_core.eq("ok") & part.y_true.gt(0)]
            for keys, group in part.groupby(GROUP):
                group = group.sort_values("origin_date")
                actual = group.y_true.to_numpy()
                full_prediction = group.rv_forecast_pct2_full.to_numpy()
                core_prediction = group.rv_forecast_pct2_core.to_numpy()
                full_loss = qlike_loss(actual, full_prediction)
                core_loss = qlike_loss(actual, core_prediction)
                dm = dm_test(pd.Series(full_loss), pd.Series(core_loss), h=int(horizon), dates=group.origin_date,
                    min_n=config["backend1"]["evaluation"]["dm_min_observations"])
                row = dict(zip(GROUP, keys), model=name, auxiliary_features="log_qv,log_turn_rel",
                           n_common=len(group), QLIKE_full=float(full_loss.mean()), QLIKE_core=float(core_loss.mean()),
                           QLIKE_full_minus_core=float((full_loss-core_loss).mean()),
                           dm_stat=dm["stat"], dm_p_value=dm["p_value"], dm_status=dm["status"],
                           same_hyperparameters=True, same_training_rows=True)
                for label, prediction in [("full", full_prediction), ("core", core_prediction)]:
                    row["RMSE_"+label] = float(np.sqrt(np.mean((prediction-actual)**2)))
                    row["MAE_"+label] = float(np.mean(np.abs(prediction-actual)))
                records.append(row)
    return pd.DataFrame(records)


def shap_figures(shap, predictors, directory):
    summaries = []
    for keys, group in shap.groupby(GROUP):
        symbol, window, horizon = keys
        means = {name: float(group["shap_"+name].abs().mean()) for name in predictors}
        order = sorted(predictors, key=means.get)
        for feature in predictors:
            summaries.append(dict(zip(GROUP, keys), feature=feature, mean_abs_shap=means[feature],
                                  n_origins=len(group), scale="raw_log_RV", method="native_exact_TreeSHAP"))
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), layout="constrained")
        axes[0].barh(order, [means[name] for name in order], color="#377eb8")
        axes[0].set_xlabel("Mean absolute SHAP (log RV)")
        rng = np.random.default_rng(20261023)
        for position, feature in enumerate(order):
            color = group["value_"+feature].rank(pct=True).to_numpy()
            points = axes[1].scatter(group["shap_"+feature], position+rng.uniform(-.23, .23, len(group)),
                                     c=color, cmap="coolwarm", vmin=0, vmax=1, s=5, alpha=.45, rasterized=True)
        axes[1].set_yticks(range(len(order)), order)
        axes[1].axvline(0, color="gray", linewidth=.7)
        axes[1].set_xlabel("Local SHAP contribution (log RV)")
        fig.colorbar(points, ax=axes[1], label="Feature percentile (descriptive)", shrink=.7)
        fig.suptitle(f"{symbol} | {window} | h={horizon} | OOS TreeSHAP from active refit models")
        fig.savefig(directory/f"backend3_{symbol}_{window}_h{horizon}_shap.png", dpi=135)
        plt.close(fig)
    return pd.DataFrame(summaries)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-holdout", action="store_true")
    args = parser.parse_args(argv)
    segment = "holdout" if args.final_holdout else "evaluation"
    config, options = load_config(), load_ml_config()
    dirs = locations(segment)
    dataset = pd.read_parquet(ROOT/"data/processed/dataset.parquet")
    meta = json.loads((ROOT/"data/processed/dataset_meta.json").read_text(encoding="utf-8"))
    if sha256(ROOT/"data/processed/dataset.parquet") != meta["dataset_sha256"] or protocol_hash(config) != meta["protocol_sha256"]:
        raise ValueError("Stale dataset/protocol for ML analysis")
    selection = json.loads(LOCK.read_text(encoding="utf-8"))
    run = json.loads((dirs["diagnostics"]/"run_summary.json").read_text(encoding="utf-8"))
    if selection["warmup_fingerprint"] != warmup_fingerprint(dataset, config, options):
        raise ValueError("Changed warmup selection inputs")
    if run["ml_config_sha256"] != ml_config_hash() or run["selection_sha256"] != sha256(LOCK):
        raise ValueError("Stale ML run metadata")
    for path, digest in run["input_forecast_sha256"].items():
        if sha256(ROOT/path) != digest:
            raise ValueError("Changed preceding-backend forecast: "+path)
    tables = ROOT/("outputs/holdout_tables" if args.final_holdout else "outputs/tables")
    figures = ROOT/("outputs/holdout_figures" if args.final_holdout else "outputs/figures")
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    frames = {}
    checks = []
    for name in ["enet", "xgboost", "enet_core", "xgboost_core", options["combination"]["name"]]:
        folder = dirs["ablation"] if name.endswith("_core") else dirs["forecasts"]
        pieces = []
        for symbol in config["data"]["symbols"]:
            path = folder/f"{symbol}_{name}.parquet"
            frame = pd.read_parquet(path)
            errors = validate_forecasts(frame, dataset, config, meta["dataset_sha256"], name)
            if errors:
                raise ValueError(errors)
            if not frame.model.eq(name).all() or not frame.symbol.eq(symbol).all():
                raise ValueError("Unexpected model/symbol identity in "+str(path))
            schedule = pd.read_parquet(ROOT/"data/processed/forecast_schedule.parquet")
            expected_keys = schedule.loc[schedule.symbol.eq(symbol)&schedule.target_segment.eq(segment), KEY]
            actual_keys = frame[KEY]
            if set(map(tuple, actual_keys.to_numpy())) != set(map(tuple, expected_keys.to_numpy())):
                raise ValueError("Forecast rows do not cover the complete agreed schedule")
            if not frame.model_config_sha256.eq(ml_config_hash()).all() or not frame.selection_sha256.eq(sha256(LOCK)).all():
                raise ValueError("Stale model settings in "+str(path))
            if not name.endswith("_core"):
                vol = pd.read_parquet(dirs["volatility"]/path.name)
                ok = vol.status.eq("ok")
                np.testing.assert_allclose(vol.loc[ok, "sigma_pct"]**2, vol.loc[ok, "variance_pct2"], rtol=1e-10)
                if not vol.student_t_scale_pct.isna().all():
                    raise ValueError("FHS models cannot claim a Student-t scale")
            checks.append({"symbol": symbol, "model": name, "rows": len(frame),
                           "successful": int(frame.status.eq("ok").sum()), "sha256": sha256(path)})
            pieces.append(frame)
        frames[name] = pd.concat(pieces, ignore_index=True)
    fit = pd.read_csv(dirs["diagnostics"]/"fit_diagnostics.csv")
    if fit.duplicated(["symbol", "model", "window", "horizon_days", "refit_origin"]).any():
        raise ValueError("Duplicate refit diagnostics")
    for name in ["enet", "xgboost"]:
        left = fit.loc[fit.model.eq(name)].set_index(GROUP+["refit_origin"]).sort_index()
        right = fit.loc[fit.model.eq(name+"_core")].set_index(GROUP+["refit_origin"]).sort_index()
        pd.testing.assert_frame_equal(left[["train_rows_sha256", "n_train"]], right[["train_rows_sha256", "n_train"]])
    ablation = volume_ablation(dataset, frames, config, segment)
    ablation.to_csv(tables/"backend3_volume_ablation.csv", index=False)
    statuses = [{"variables": "volume", "status": "completed", "reason": "matched rows and fixed full-model settings"},
                {"variables": "VIX", "status": "blocked_unverified_point_in_time", "reason": "historical release/vintage unavailable"},
                {"variables": "USD", "status": "blocked_unverified_point_in_time", "reason": "historical release/vintage unavailable"},
                {"variables": "GRU", "status": "excluded_user_scope", "reason": "optional work deferred by user"}]
    pd.DataFrame(statuses).to_csv(tables/"backend3_scope_status.csv", index=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    for symbol, group in ablation.groupby("symbol"):
        fig, axes = plt.subplots(2, 2, figsize=(10, 6), layout="constrained")
        for ax, ((window, horizon), part) in zip(axes.flat, group.groupby(["window", "horizon_days"])):
            x = np.arange(len(part))
            ax.bar(x-.18, part.QLIKE_core, .36, label="Without volume")
            ax.bar(x+.18, part.QLIKE_full, .36, label="With volume")
            ax.set_xticks(x, part.model)
            ax.set_title(f"{window}, h={horizon}")
            ax.set_ylabel("QLIKE (lower is better)")
            ax.legend(fontsize=8)
        fig.suptitle(f"{symbol} | matched-sample volume ablation")
        fig.savefig(figures/f"backend3_{symbol}_volume_ablation.png", dpi=135)
        plt.close(fig)
    shap = pd.read_parquet(dirs["diagnostics"]/"oos_shap.parquet")
    predictors = options["features"]["core"]+options["features"]["volume"]
    if not np.isfinite(shap[["shap_"+name for name in predictors]+["base_value", "raw_log_prediction"]]).all().all():
        raise ValueError("Nonfinite SHAP contributions")
    reconstructed = shap[["shap_"+name for name in predictors]].sum(axis=1)+shap.base_value
    np.testing.assert_allclose(reconstructed, shap.raw_log_prediction, rtol=1e-5, atol=5e-5)
    expected = frames["xgboost"].loc[frames["xgboost"].status.eq("ok")]
    if shap.duplicated(KEY).any() or len(shap) != len(expected):
        raise ValueError("SHAP coverage differs from successful XGBoost forecasts")
    merged = shap.merge(expected[KEY+["fit_signature", "rv_forecast_pct2"]], on=KEY, suffixes=("", "_forecast"), validate="one_to_one")
    if len(merged) != len(expected) or not merged.fit_signature.eq(merged.fit_signature_forecast).all():
        raise ValueError("SHAP was not computed from the active origin model")
    np.testing.assert_allclose(merged.rv_forecast_pct2, merged.rv_forecast_pct2_forecast, rtol=1e-10)
    importance = shap_figures(shap, predictors, figures)
    importance.to_csv(tables/"backend3_shap_importance.csv", index=False)
    result = {"status": "passed", "segment": segment, "protocol_sha256": protocol_hash(config),
              "dataset_sha256": meta["dataset_sha256"], "ml_config_sha256": ml_config_hash(),
              "selection_sha256": sha256(LOCK), "checks": checks, "fit_count": len(fit),
              "fit_failures": int(fit.fit_status.ne("ok").sum()), "shap_rows": len(shap),
              "shap_max_identity_error": float(shap.shap_identity_error.max()),
              "matched_ablation_training_rows": True, "selection_uses_evaluation": False,
              "macro_predictive_use": False, "macro_ablation_status": "blocked_unverified_point_in_time",
              "gru_status": "excluded_user_scope", "holdout_scored": args.final_holdout,
              "external_independent_review": "pending_team_review"}
    save_json(dirs["diagnostics"]/"validation.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
