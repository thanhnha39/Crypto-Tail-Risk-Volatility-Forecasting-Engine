"""Frozen ML models, matched volume ablation and equal-weight core4 combination."""
import argparse
import json
import pandas as pd
from src.data.download import sha256, save_json
from src.evaluation.validate import validate_forecasts
from src.evaluation.walkforward import Task, walk_forward
from src.models.combine import combine_forecasts
from src.models.enet import ElasticNetRV, ElasticNetCore
from src.models.xgb import XGBoostRV, XGBoostCore
from src.models.ml_common import load_ml_config, ml_config_hash
from src.models.tune_ml import prepare_selection, LOCK
from src.models.run import export_volatility, export_residuals
from src.utils.config import ROOT, load_config, protocol_hash
from src.utils.io import write_table

VARIANTS = [(ElasticNetRV, "enet", False), (XGBoostRV, "xgboost", False),
            (ElasticNetCore, "enet", True), (XGBoostCore, "xgboost", True)]


def locations(segment):
    suffix = "" if segment == "evaluation" else "_holdout"
    return {"forecasts": ROOT/f"outputs/forecasts{suffix}",
            "volatility": ROOT/f"outputs/volatility{suffix}",
            "ablation": ROOT/f"outputs/ablation{suffix}/forecasts",
            "diagnostics": ROOT/f"outputs/diagnostics{suffix}/backend3"}


def validate_prerequisites(dataset, meta, config, segment):
    checksums = {}
    for symbol in config["data"]["symbols"]:
        for name in ["har_rv", "garch", "gjr_garch"]:
            path = locations(segment)["forecasts"]/f"{symbol}_{name}.parquet"
            if not path.exists():
                raise ValueError("Run the preceding backend for this segment first: "+str(path))
            frame = pd.read_parquet(path)
            if not frame.model.eq(name).all() or not frame.symbol.eq(symbol).all():
                raise ValueError("Preceding backend file has an unexpected model/symbol")
            errors = validate_forecasts(frame, dataset, config, meta["dataset_sha256"], name)
            if errors:
                raise ValueError(errors)
            checksums[path.relative_to(ROOT).as_posix()] = sha256(path)
    return checksums


def run(segment="evaluation"):
    if segment not in ["evaluation", "holdout"]:
        raise ValueError("Unknown segment")
    config, options = load_config(), load_ml_config()
    path = ROOT/"data/processed/dataset.parquet"
    meta = json.loads((path.parent/"dataset_meta.json").read_text(encoding="utf-8"))
    if sha256(path) != meta["dataset_sha256"] or protocol_hash(config) != meta["protocol_sha256"]:
        raise ValueError("Stale shared dataset")
    for name, expected in meta["inputs_sha256"].items():
        if sha256(ROOT/name) != expected:
            raise ValueError("Changed source input: "+name)
    dataset = pd.read_parquet(path)
    inputs = validate_prerequisites(dataset, meta, config, segment)
    selection = prepare_selection(dataset, meta, config, options)
    dirs = locations(segment)
    for folder in dirs.values():
        folder.mkdir(parents=True, exist_ok=True)
    diagnostics, shap_records, main_outputs, outputs = [], [], [], []
    for symbol, data in dataset.groupby("symbol"):
        full_frames = {}
        for cls, base_name, core in VARIANTS:
            chunks = []
            for scheme in ["rolling", "expanding"]:
                for horizon in [1, 7]:
                    settings = selection["selected_parameters"][symbol][str(horizon)][base_name]
                    def factory(cls=cls, settings=settings, core=core, base_name=base_name):
                        return cls(settings=settings, options=options, diagnostics=diagnostics,
                            shap_records=shap_records if base_name=="xgboost" and not core else None)
                    forecast = walk_forward(data, factory, Task(horizon), config, scheme, segment)
                    chunks.append(forecast)
                    print(f"{symbol}/{cls.name}/{scheme}/h{horizon}: {int(forecast.status.eq('ok').sum())}/{len(forecast)} forecasts", flush=True)
            frame = pd.concat(chunks, ignore_index=True)
            frame["protocol_sha256"] = protocol_hash(config)
            frame["dataset_sha256"] = meta["dataset_sha256"]
            frame["model_config_sha256"] = ml_config_hash()
            frame["selection_sha256"] = sha256(LOCK)
            frame["feature_variant"] = "without_volume_matched_rows" if core else "with_volume"
            errors = validate_forecasts(frame, dataset, config, meta["dataset_sha256"], cls.name)
            if errors:
                raise ValueError(errors)
            folder = dirs["ablation"] if core else dirs["forecasts"]
            write_table(frame, folder/f"{symbol}_{cls.name}.parquet")
            if not core:
                export_volatility(frame, dirs["volatility"])
                full_frames[base_name] = frame
                main_outputs.append(frame)
            outputs.append(frame)
        pieces = {name: full_frames[name] if name in full_frames else
            pd.read_parquet(dirs["forecasts"]/f"{symbol}_{name}.parquet")
            for name in options["combination"]["components"]}
        combined = combine_forecasts(pieces, options["combination"]["components"], options["combination"]["name"])
        combined["model_config_sha256"] = ml_config_hash()
        combined["selection_sha256"] = sha256(LOCK)
        errors = validate_forecasts(combined, dataset, config, meta["dataset_sha256"], "core4 combination")
        if errors:
            raise ValueError(errors)
        write_table(combined, dirs["forecasts"]/f"{symbol}_{options['combination']['name']}.parquet")
        export_volatility(combined, dirs["volatility"])
        main_outputs.append(combined)
    pd.DataFrame(diagnostics).to_csv(dirs["diagnostics"]/"fit_diagnostics.csv", index=False)
    write_table(pd.DataFrame(shap_records), dirs["diagnostics"]/"oos_shap.parquet")
    write_table(export_residuals(pd.concat(main_outputs, ignore_index=True), dataset),
                dirs["diagnostics"]/"oos_standardized_residuals.parquet")
    save_json(dirs["diagnostics"]/"run_summary.json", {
        "segment": segment, "models": [cls.name for cls, _, _ in VARIANTS],
        "ml_config_sha256": ml_config_hash(), "selection_sha256": sha256(LOCK),
        "protocol_sha256": protocol_hash(config), "dataset_sha256": meta["dataset_sha256"],
        "input_forecast_sha256": inputs, "fit_count": len(diagnostics), "shap_rows": len(shap_records),
        "forecast_rows_including_ablation": sum(len(frame) for frame in outputs),
        "status_counts": pd.concat(outputs).status.value_counts().to_dict(),
        "holdout_scored": False, "holdout_forecasted": segment=="holdout", "gru_enabled": False,
        "macro_predictive_use": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-holdout", action="store_true")
    args = parser.parse_args()
    lock = ROOT/"outputs/final_holdout_backend3.json"
    if args.final_holdout:
        if lock.exists() or not LOCK.exists():
            raise ValueError("Holdout was already started or warmup selection is not locked")
        config = load_config()
        dataset = pd.read_parquet(ROOT/"data/processed/dataset.parquet")
        meta = json.loads((ROOT/"data/processed/dataset_meta.json").read_text())
        validate_prerequisites(dataset, meta, config, "holdout")
        save_json(lock, {"state": "started", "ml_config_sha256": ml_config_hash()})
    run("holdout" if args.final_holdout else "evaluation")
    if args.final_holdout:
        save_json(lock, {"state": "completed", "ml_config_sha256": ml_config_hash()})


if __name__ == "__main__":
    main()
