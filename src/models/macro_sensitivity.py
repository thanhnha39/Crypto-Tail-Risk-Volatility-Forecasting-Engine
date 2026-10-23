"""Frozen-parameter, matched-sample VIX/USD ablations outside the main model comparison."""
import argparse
import json
import os
import numpy as np
import pandas as pd
from src.data.download import sha256, save_json
from src.data.macro_vintages import load_verified_macro, OUTPUT as MACRO_DATA
from src.evaluation.walkforward import walk_forward, Task
from src.evaluation.validate import validate_forecasts, truth_table
from src.evaluation.metrics import add_losses, summarize
from src.evaluation.dm import dm_test
from src.models.enet import ElasticNetRV
from src.models.xgb import XGBoostRV
from src.models.ml_common import load_ml_config, ml_config_hash
from src.models.tune_ml import prepare_selection, LOCK
from src.utils.config import ROOT, load_config, protocol_hash

DIRECTORY = ROOT/"outputs/sensitivity/macro"
VARIANTS = {"macro_base": [], "vix": ["log_vix_l1"], "usd": ["log_usd_l1"],
            "vix_usd": ["log_vix_l1", "log_usd_l1"]}
GROUP = ["symbol", "window", "horizon_days"]


def make_model(cls, settings, options, variant, diagnostics=None):
    model = cls(settings=settings, options=options, diagnostics=diagnostics)
    baseline = list(model.features)
    model.name = cls.name+"_"+variant
    model.features = baseline+VARIANTS["vix_usd"]
    model.predictors = baseline+VARIANTS[variant]
    model.verified_macro = True
    return model


def tables(forecasts, dataset, config):
    joined = forecasts.merge(truth_table(dataset, [1, 7]), on=["symbol", "origin_date", "horizon_days"], validate="many_to_one")
    joined = joined.loc[joined.target_segment.eq("evaluation")]
    records, coverage = [], []
    for keys, group in joined.groupby(GROUP):
        names = sorted(group.model.unique())
        eligible = group.loc[group.status.eq("ok") & group.y_true.gt(0) & np.isfinite(group.y_true)]
        counts = eligible.groupby("origin_date").model.nunique()
        dates = counts.index[counts.eq(len(names))]
        sample = add_losses(eligible.loc[eligible.origin_date.isin(dates)])
        for name, part in group.groupby("model"):
            coverage.append(dict(zip(GROUP, keys), model=name, requested=len(part),
                successful=int(part.status.eq("ok").sum()), n_common=len(dates)))
        for base in ["enet", "xgboost"]:
            reference = sample.loc[sample.model.eq(base+"_macro_base")].set_index("origin_date").sort_index()
            for variant in VARIANTS:
                part = sample.loc[sample.model.eq(base+"_"+variant)].set_index("origin_date").sort_index()
                pd.testing.assert_index_equal(reference.index, part.index)
                if part.empty:
                    raise ValueError("Empty matched macro sample")
                np.testing.assert_allclose(reference.y_true, part.y_true)
                score = summarize(part)
                dm = dm_test(part.qlike, reference.qlike, h=int(keys[2]), dates=part.index,
                    min_n=config["backend1"]["evaluation"]["dm_min_observations"])
                records.append(dict(zip(GROUP, keys), model=base, feature_set=variant, **score.to_dict(),
                    QLIKE_minus_without_macro=float(part.qlike.mean()-reference.qlike.mean()),
                    dm_stat=dm["stat"] if variant != "macro_base" else np.nan,
                    dm_p_value=dm["p_value"] if variant != "macro_base" else np.nan,
                    dm_status=dm["status"] if variant != "macro_base" else "reference",
                    sample="same_dates_all_eight_variants", same_training_rows=True,
                    hyperparameters="unchanged_full_model_warmup_lock", main_model=False))
    return pd.DataFrame(records), pd.DataFrame(coverage)


def analyze(dataset, config, meta):
    frames = []
    schedule = pd.read_parquet(ROOT/"data/processed/forecast_schedule.parquet")
    schedule = schedule.loc[schedule.target_segment.eq("evaluation")]
    paths = sorted((DIRECTORY/"forecasts").glob("*.parquet"))
    if len(paths) != 8*len(config["data"]["symbols"]):
        raise ValueError("Unexpected macro forecast file count")
    for path in paths:
        frame = pd.read_parquet(path)
        errors = validate_forecasts(frame, dataset, config, meta["dataset_sha256"], path.name)
        if errors:
            raise ValueError(errors)
        if not frame.macro_dataset_sha256.eq(sha256(MACRO_DATA)).all() or not frame.selection_sha256.eq(sha256(LOCK)).all():
            raise ValueError("Stale macro forecast provenance")
        if frame.symbol.nunique() != 1 or frame.model.nunique() != 1 or path.stem != frame.symbol.iloc[0]+"_"+frame.model.iloc[0]:
            raise ValueError("Macro forecast identity mismatch")
        keys = ["symbol", "window", "horizon_days", "origin_date"]
        expected = schedule.loc[schedule.symbol.eq(frame.symbol.iloc[0]), keys]
        if set(map(tuple, expected.to_numpy())) != set(map(tuple, frame[keys].to_numpy())):
            raise ValueError("Incomplete macro forecast schedule")
        frames.append(frame)
    forecasts = pd.concat(frames, ignore_index=True)
    if forecasts.model.nunique() != 8 or forecasts.symbol.nunique() != len(config["data"]["symbols"]):
        raise ValueError("Incomplete macro models/symbols")
    fit = pd.read_csv(DIRECTORY/"fit_diagnostics.csv")
    for _, group in fit.groupby(GROUP+["refit_origin"]):
        if group.train_rows_sha256.nunique() != 1 or group.n_train.nunique() != 1 or group.model.nunique() != 8:
            raise ValueError("Macro ablation training samples differ")
    comparison, coverage = tables(forecasts, dataset, config)
    comparison.to_csv(ROOT/"outputs/tables/backend3_macro_ablation.csv", index=False)
    coverage.to_csv(DIRECTORY/"coverage.csv", index=False)
    save_json(DIRECTORY/"validation.json", dict(status="passed", segment="evaluation",
        macro_dataset_sha256=sha256(MACRO_DATA), dataset_sha256=meta["dataset_sha256"],
        protocol_sha256=protocol_hash(config), selection_sha256=sha256(LOCK), ml_config_sha256=ml_config_hash(),
        fit_count=len(fit), fit_failures=int(fit.fit_status.ne("ok").sum()),
        same_training_rows=True, forecast_rows=len(forecasts), comparison_rows=len(comparison),
        fit_diagnostics_sha256=sha256(DIRECTORY/"fit_diagnostics.csv"),
        main_model_macro_use=False, holdout_scored=False, hyperparameters_retuned=False,
        inputs={p.name:sha256(p) for p in sorted((DIRECTORY/"forecasts").glob("*.parquet"))}))
    return comparison


def run_variant(job):
    symbol, data, base_name, variant, selected, options, config, meta = job
    cls = ElasticNetRV if base_name == "enet" else XGBoostRV
    chunks, diagnostics = [], []
    for window in ["rolling", "expanding"]:
        for horizon in [1, 7]:
            settings = selected[str(horizon)][cls.name]
            def factory(settings=settings):
                return make_model(cls, settings, options, variant, diagnostics)
            frame = walk_forward(data, factory, Task(horizon), config, window, "evaluation")
            chunks.append(frame)
            print(f"macro {symbol}/{base_name}/{variant}/{window}/h{horizon}: {int(frame.status.eq('ok').sum())}", flush=True)
    result = pd.concat(chunks, ignore_index=True)
    result["dataset_sha256"] = meta["dataset_sha256"]
    result["protocol_sha256"] = protocol_hash(config)
    result["selection_sha256"] = sha256(LOCK)
    result["model_config_sha256"] = ml_config_hash()
    result["macro_dataset_sha256"] = sha256(MACRO_DATA)
    result.to_parquet(DIRECTORY/"forecasts"/f"{symbol}_{base_name}_{variant}.parquet", index=False)
    refits = DIRECTORY/"refits"
    refits.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(diagnostics).to_csv(refits/f"{symbol}_{base_name}_{variant}.csv", index=False)
    return diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", choices=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--model", choices=["enet", "xgboost"])
    parser.add_argument("--variant", choices=list(VARIANTS))
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    if args.analyze_only and (args.symbol or args.model or args.variant):
        parser.error("Analyze the complete sensitivity set without task filters")
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    config, options = load_config(), load_ml_config()
    path = ROOT/"data/processed/dataset.parquet"
    meta = json.loads(path.with_name("dataset_meta.json").read_text(encoding="utf-8"))
    if sha256(path) != meta["dataset_sha256"] or protocol_hash(config) != meta["protocol_sha256"]:
        raise ValueError("Stale shared dataset")
    original = pd.read_parquet(path)
    selection = prepare_selection(original, meta, config, options)
    dataset = load_verified_macro(original)
    (DIRECTORY/"forecasts").mkdir(parents=True, exist_ok=True)
    if args.analyze_only:
        refits = sorted((DIRECTORY/"refits").glob("*.csv"))
        if len(refits) != 16:
            raise ValueError("Run all sixteen model/coin/feature variants before analysis")
        fit = pd.concat([pd.read_csv(p) for p in refits], ignore_index=True)
        fit = fit.sort_values(["symbol", "model", "window", "horizon_days", "refit_origin"])
        fit.to_csv(DIRECTORY/"fit_diagnostics.csv", index=False)
        print(f"Macro sensitivity verified: {len(analyze(dataset, config, meta))} paired score rows", flush=True)
        return
    jobs = []
    for symbol, data in dataset.groupby("symbol"):
        if args.symbol and args.symbol != symbol:
            continue
        for base_name in ["enet", "xgboost"]:
            if args.model and args.model != base_name:
                continue
            for variant in VARIANTS:
                if args.variant and args.variant != variant:
                    continue
                jobs.append((symbol, data, base_name, variant, selection["selected_parameters"][symbol], options, config, meta))
    diagnostics = []
    for job in jobs:
        diagnostics.extend(run_variant(job))
    if args.symbol or args.model or args.variant:
        print("Filtered tasks saved; run --analyze-only after all tasks finish", flush=True)
        return
    diagnostics = sorted(diagnostics, key=lambda row: (row["symbol"], row["model"], row["window"], row["horizon_days"], str(row["refit_origin"])))
    pd.DataFrame(diagnostics).to_csv(DIRECTORY/"fit_diagnostics.csv", index=False)
    table = analyze(dataset, config, meta)
    print(f"Macro sensitivity verified: {len(table)} paired score rows", flush=True)


if __name__ == "__main__":
    main()
